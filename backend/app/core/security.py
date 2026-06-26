import asyncio
import json
import logging
from typing import Any, Dict, List
from urllib.request import urlopen

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import get_settings
from app.models.enums import RoleName
from app.schemas.auth import UserContext


bearer_scheme = HTTPBearer(auto_error=True)
_jwks_client: PyJWKClient | None = None
logger = logging.getLogger(__name__)


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        openid_config_url = f"https://login.microsoftonline.com/{settings.tenant_id}/v2.0/.well-known/openid-configuration"
        with urlopen(openid_config_url) as response:
            config = json.loads(response.read())
        _jwks_client = PyJWKClient(config["jwks_uri"])
    return _jwks_client


async def validate_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    jwks_client = _get_jwks_client()
    allowed_audiences = {
        settings.api_audience,
        settings.client_id,
        f"api://{settings.client_id}",
    }
    allowed_issuers = {
        f"https://login.microsoftonline.com/{settings.tenant_id}/v2.0",
        f"https://login.microsoftonline.com/{settings.tenant_id}/",
        f"https://sts.windows.net/{settings.tenant_id}/",
    }

    def _decode() -> Dict[str, Any]:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,
                "verify_iss": False,
            },
        )

        aud = claims.get("aud")
        iss = claims.get("iss")
        tid = claims.get("tid")

        # Preferred strict checks
        if aud in allowed_audiences and iss in allowed_issuers:
            return claims

        # Local fallback: allow tenant-scoped Entra tokens when audience format differs.
        if tid == settings.tenant_id and iss in allowed_issuers:
            logger.warning(
                "Using tenant fallback token validation for aud=%s iss=%s; ensure API scope/audience is configured correctly.",
                aud,
                iss,
            )
            return claims

        raise ValueError(f"Invalid token claims: aud={aud}, iss={iss}, tid={tid}")

    try:
        return await asyncio.to_thread(_decode)
    except Exception as exc:
        logger.warning("Access token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc


def extract_roles(claims: Dict[str, Any]) -> List[str]:
    roles = claims.get("roles", [])
    if not roles:
        roles = claims.get("extension_Roles", [])
    return roles if isinstance(roles, list) else []


def _normalize_email_candidate(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().lower()
    if normalized.startswith("smtp:"):
        normalized = normalized[5:]

    # Guest accounts can appear as user_domain.com#EXT#@tenant.onmicrosoft.com.
    # Convert that pattern back to user@domain.com for stable matching.
    marker = "#ext#@"
    if marker in normalized:
        local = normalized.split(marker, 1)[0]
        if "_" in local:
            local_user, local_domain = local.split("_", 1)
            candidate = f"{local_user}@{local_domain}"
            if "@" in candidate:
                return candidate

    return normalized if "@" in normalized else None


def apply_role_overrides(email: str | None, roles: List[str]) -> List[str]:
    normalized_roles = list(roles)
    normalized_email = _normalize_email_candidate(email)
    if not normalized_email:
        return normalized_roles

    settings = get_settings()
    if normalized_email in settings.manager_override_email_set and RoleName.MANAGER.value not in normalized_roles:
        normalized_roles.append(RoleName.MANAGER.value)

    return normalized_roles


def extract_email(claims: Dict[str, Any]) -> str | None:
    for key in ("preferred_username", "upn", "email", "unique_name"):
        value = claims.get(key)
        if isinstance(value, str):
            normalized = _normalize_email_candidate(value)
            if normalized:
                return normalized

    emails = claims.get("emails")
    if isinstance(emails, list):
        for value in emails:
            if isinstance(value, str):
                normalized = _normalize_email_candidate(value)
                if normalized:
                    return normalized

    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> UserContext:
    token = credentials.credentials
    claims = await validate_access_token(token)

    oid = claims.get("oid")
    if not oid:
        raise HTTPException(status_code=401, detail="Missing oid claim")

    email = extract_email(claims)

    return UserContext(
        oid=oid,
        email=email,
        name=claims.get("name"),
        roles=apply_role_overrides(email, extract_roles(claims)),
        access_token=token,
    )


def require_roles(*required_roles: str):
    async def checker(user: UserContext = Security(get_current_user)) -> UserContext:
        if not required_roles:
            return user

        matched = any(role in user.roles for role in required_roles)
        if not matched:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return checker

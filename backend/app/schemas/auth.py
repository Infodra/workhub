from typing import List

from pydantic import BaseModel, EmailStr


class UserContext(BaseModel):
    oid: str
    email: EmailStr | None = None
    name: str | None = None
    roles: List[str] = []
    access_token: str

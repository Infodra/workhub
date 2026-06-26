import { Configuration, LogLevel, PublicClientApplication } from "@azure/msal-browser";

const clientId = process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || "";
const tenantId = process.env.NEXT_PUBLIC_AZURE_TENANT_ID || "";
const redirectUri = process.env.NEXT_PUBLIC_AZURE_REDIRECT_URI || "http://localhost:3000";

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (_level, _message, _containsPii) => {},
      piiLoggingEnabled: false,
      logLevel: LogLevel.Warning,
    },
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

let initializePromise: Promise<void> | null = null;

export async function ensureMsalInitialized(): Promise<void> {
  if (!initializePromise) {
    initializePromise = (async () => {
      await msalInstance.initialize();
      const result = await msalInstance.handleRedirectPromise();
      if (result?.account) {
        msalInstance.setActiveAccount(result.account);
      } else if (!msalInstance.getActiveAccount()) {
        const accounts = msalInstance.getAllAccounts();
        if (accounts.length === 1) {
          msalInstance.setActiveAccount(accounts[0]);
        }
      }
    })();
  }
  await initializePromise;
}

export const loginRequest = {
  scopes: ["openid", "profile", "email"],
  prompt: "select_account",
};

export const apiTokenRequest = {
  scopes: [process.env.NEXT_PUBLIC_AZURE_API_SCOPE || ""].filter(Boolean),
};

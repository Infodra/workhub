import axios from "axios";
import { AccountInfo } from "@azure/msal-browser";

import { apiTokenRequest, ensureMsalInitialized, msalInstance } from "@/lib/msal";

const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL;

export const api = axios.create({
  baseURL,
  timeout: 20000,
});

type RequestOptions = {
  timeoutMs?: number;
};

export async function getAccessToken(account: AccountInfo): Promise<string> {
  await ensureMsalInitialized();
  const response = await msalInstance.acquireTokenSilent({
    ...apiTokenRequest,
    account,
  });
  return response.accessToken;
}

export async function authGet<T>(path: string, account: AccountInfo): Promise<T> {
  const token = await getAccessToken(account);
  const res = await api.get<T>(path, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return res.data;
}

export async function authPost<T>(path: string, data: unknown, account: AccountInfo, options?: RequestOptions): Promise<T> {
  const token = await getAccessToken(account);
  const res = await api.post<T>(path, data, {
    timeout: options?.timeoutMs,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return res.data;
}

export async function authPut<T>(path: string, data: unknown, account: AccountInfo, options?: RequestOptions): Promise<T> {
  const token = await getAccessToken(account);
  const res = await api.put<T>(path, data, {
    timeout: options?.timeoutMs,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return res.data;
}

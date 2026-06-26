"use client";

import { useMemo } from "react";
import { useMsal } from "@azure/msal-react";
import { useQuery } from "@tanstack/react-query";

import { authGet } from "@/lib/api";
import { AttendanceRecord } from "@/types";

const managerOverrideEmails = new Set(
  (process.env.NEXT_PUBLIC_MANAGER_OVERRIDE_EMAILS || "")
    .split(",")
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean),
);

function decodeRoles(idTokenClaims: Record<string, unknown> | undefined): string[] {
  const value = idTokenClaims?.roles;
  if (Array.isArray(value)) {
    return value.map(String);
  }
  return [];
}

function getAccountEmail(account: { username?: string; idTokenClaims?: unknown } | null): string {
  if (!account) {
    return "";
  }

  const claims = (account.idTokenClaims || {}) as Record<string, unknown>;
  const claimEmail =
    (typeof claims.preferred_username === "string" && claims.preferred_username) ||
    (typeof claims.upn === "string" && claims.upn) ||
    (typeof claims.email === "string" && claims.email) ||
    (typeof claims.unique_name === "string" && claims.unique_name) ||
    "";

  return String(claimEmail || account.username || "").toLowerCase();
}

export function useCurrentAccount() {
  const { accounts } = useMsal();
  return accounts[accounts.length - 1] ?? null;
}

export function useRole() {
  const account = useCurrentAccount();
  return useMemo(() => {
    const roles = decodeRoles(account?.idTokenClaims as Record<string, unknown> | undefined);
    const email = getAccountEmail(account);
    if (email && managerOverrideEmails.has(email) && !roles.includes("Manager")) {
      return [...roles, "Manager"];
    }
    return roles;
  }, [account]);
}

export function useDashboardQuery() {
  const account = useCurrentAccount();
  return useQuery({
    queryKey: ["dashboard", account?.homeAccountId],
    enabled: Boolean(account),
    queryFn: () => authGet<Record<string, unknown>>("/dashboard", account!),
  });
}

export function useTodayAttendanceQuery() {
  const account = useCurrentAccount();
  return useQuery({
    queryKey: ["attendance-today", account?.homeAccountId],
    enabled: Boolean(account),
    queryFn: () => authGet<AttendanceRecord[]>("/attendance/today", account!),
  });
}

export function useMonthlyAttendanceQuery(month: string) {
  const account = useCurrentAccount();
  return useQuery({
    queryKey: ["attendance-month", month, account?.homeAccountId],
    enabled: Boolean(account),
    queryFn: () => authGet<AttendanceRecord[]>(`/attendance/month?month=${month}`, account!),
  });
}

export function useEmployeeMonthlyAttendanceQuery(employeeEmail: string, month: string) {
  const account = useCurrentAccount();
  return useQuery({
    queryKey: ["attendance-employee-month", employeeEmail, month, account?.homeAccountId],
    enabled: Boolean(account && employeeEmail && month),
    queryFn: () => authGet<AttendanceRecord[]>(`/attendance/${encodeURIComponent(employeeEmail)}?month=${month}`, account!),
  });
}

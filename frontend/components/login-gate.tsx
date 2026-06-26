"use client";

import { InteractionStatus } from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";
import { useEffect, useRef } from "react";

import { ensureMsalInitialized, loginRequest } from "@/lib/msal";

export function LoginGate({ children }: { children: React.ReactNode }) {
  const { instance, accounts, inProgress } = useMsal();
  const redirectStartedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function startLogin() {
      await ensureMsalInitialized();

      if (!cancelled && accounts.length && !instance.getActiveAccount()) {
        instance.setActiveAccount(accounts[accounts.length - 1]);
      }

      if (cancelled || accounts.length) {
        return;
      }

      if (inProgress !== InteractionStatus.None || redirectStartedRef.current) {
        return;
      }

      redirectStartedRef.current = true;
      try {
        await instance.loginRedirect(loginRequest);
      } catch {
        redirectStartedRef.current = false;
      }
    }

    void startLogin();

    return () => {
      cancelled = true;
    };
  }, [accounts.length, inProgress, instance]);

  if (!accounts.length) {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center p-6">
        <div className="card rounded-2xl p-8 text-center shadow-sm">
          <h1 className="text-3xl font-extrabold">Infodra WorkHub</h1>
          <p className="mt-2 text-[color:var(--muted)]">Signing you in with Microsoft 365...</p>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}

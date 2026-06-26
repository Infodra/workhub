"use client";

import Link from "next/link";
import { useMsal } from "@azure/msal-react";

import { AttendanceChart } from "@/components/attendance-chart";
import { AttendanceTable } from "@/components/attendance-table";
import { CardGrid, StatCard } from "@/components/card-grid";
import { LoginGate } from "@/components/login-gate";
import { ThemeToggle } from "@/components/theme-toggle";
import { authPost } from "@/lib/api";
import { useCurrentAccount, useDashboardQuery, useMonthlyAttendanceQuery, useRole, useTodayAttendanceQuery } from "@/lib/hooks";

export function DashboardHome() {
  const account = useCurrentAccount();
  const { instance } = useMsal();
  const roles = useRole();
  const dashboard = useDashboardQuery();
  const today = useTodayAttendanceQuery();
  const month = new Date().toISOString().slice(0, 7);
  const monthData = useMonthlyAttendanceQuery(month);

  const rolePath = roles.includes("Admin") ? "/admin" : roles.includes("Manager") ? "/manager" : "/employee";
  const data = dashboard.data || {};

  async function triggerSync() {
    if (!account) return;
    const now = new Date();
    const endDate = now.toISOString().slice(0, 10);
    const startDate = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
    await authPost("/sync", { start_date: startDate, end_date: endDate }, account, { timeoutMs: 600000 });
    await dashboard.refetch();
    await today.refetch();
    await monthData.refetch();
  }

  return (
    <LoginGate>
      <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold">Infodra WorkHub</h1>
            <p className="text-[color:var(--muted)]">Microsoft 365 Attendance and Activity Tracker</p>
          </div>
          <div className="flex items-center gap-3">
            <Link href={rolePath} className="rounded-full bg-[color:var(--brand)] px-4 py-2 text-sm font-bold text-white shadow-glow">
              Open {roles.includes("Admin") ? "Admin" : roles.includes("Manager") ? "Manager" : "Employee"} Dashboard
            </Link>
            {roles.includes("Admin") || roles.includes("Manager") ? (
              <button className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={triggerSync} type="button">
                Run Sync
              </button>
            ) : null}
            <ThemeToggle />
            <button
              className="rounded-full border px-4 py-2 text-sm font-semibold"
              type="button"
              onClick={() => instance.logoutRedirect()}
            >
              Sign out
            </button>
          </div>
        </header>

        <CardGrid>
          <StatCard title="Your Role" value={(roles[0] || "Employee").toUpperCase()} accent="var(--brand)" />
          <StatCard title="Attendance Status" value={String(data.attendance_status || "-")} accent="var(--ok)" />
          <StatCard title="Working Hours" value={String(data.working_hours || 0)} accent="var(--brand-2)" />
          <StatCard title="Meeting Hours" value={String(data.meeting_hours || 0)} accent="var(--warn)" />
        </CardGrid>

        <section className="mt-6 grid gap-6 xl:grid-cols-2">
          <AttendanceChart data={monthData.data || []} />
          <AttendanceTable data={today.data || []} />
        </section>
      </main>
    </LoginGate>
  );
}

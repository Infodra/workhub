"use client";

import { useState } from "react";

import { CardGrid, StatCard } from "@/components/card-grid";
import { LoginGate } from "@/components/login-gate";
import { useCurrentAccount, useDashboardQuery } from "@/lib/hooks";
import { authGet } from "@/lib/api";

export default function AdminDashboardPage() {
  const account = useCurrentAccount();
  const dashboard = useDashboardQuery();
  const [reportJson, setReportJson] = useState<string>("{}");
  const data = dashboard.data || {};

  async function loadReport(type: string) {
    if (!account) return;
    const month = new Date().toISOString().slice(0, 7);
    const report = await authGet<Record<string, unknown>>(`/reports?report_type=${type}&month=${month}`, account);
    setReportJson(JSON.stringify(report, null, 2));
  }

  return (
    <LoginGate>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-extrabold">Admin Dashboard</h1>
        <p className="mt-1 text-[color:var(--muted)]">Operations, sync health, graph/sharepoint status, and reports.</p>

        <section className="mt-6">
          <CardGrid>
            <StatCard title="Total Employees" value={String(data.total_employees || 0)} accent="var(--brand)" />
            <StatCard title="Graph API" value={String(data.graph_api_status || "Unknown")} accent="var(--ok)" />
            <StatCard title="SharePoint" value={String(data.sharepoint_status || "Unknown")} accent="var(--ok)" />
            <StatCard title="Sync Last Run" value={String((data.synchronization_status as Record<string, unknown> | undefined)?.last_run || "-")} />
          </CardGrid>
        </section>

        <section className="mt-6 card rounded-2xl p-5 shadow-sm">
          <h2 className="text-xl font-bold">Reports</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={() => loadReport("daily")}>Daily Attendance</button>
            <button type="button" className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={() => loadReport("monthly")}>Monthly Attendance</button>
            <button type="button" className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={() => loadReport("late-login")}>Late Login</button>
            <button type="button" className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={() => loadReport("meeting-hours")}>Meeting Hours</button>
            <button type="button" className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={() => loadReport("leave")}>Leave Summary</button>
            <button type="button" className="rounded-full border px-4 py-2 text-sm font-semibold" onClick={() => loadReport("holiday")}>Holiday Calendar</button>
          </div>
          <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-black/80 p-4 text-xs text-green-300">{reportJson}</pre>
        </section>
      </main>
    </LoginGate>
  );
}

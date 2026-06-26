"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

import { AttendanceTable } from "@/components/attendance-table";
import { CardGrid, StatCard } from "@/components/card-grid";
import { LoginGate } from "@/components/login-gate";
import { useEmployeeMonthlyAttendanceQuery } from "@/lib/hooks";
import { AttendanceRecord } from "@/types";

function statusList(rows: AttendanceRecord[]): string[] {
  return Array.from(new Set(rows.map((row) => String(row.AttendanceStatus || "Unknown")))).sort((a, b) => a.localeCompare(b));
}

function employeeDisplayName(rows: AttendanceRecord[], email: string): string {
  return rows[0]?.EmployeeName || email;
}

function presentLikeCount(rows: AttendanceRecord[]): number {
  return rows.filter((row) => ["Present", "Late", "Half Day"].includes(String(row.AttendanceStatus || ""))).length;
}

function totalHours(rows: AttendanceRecord[]): number {
  return rows.reduce((sum, row) => sum + Number(row.WorkingHours || 0), 0);
}

function activeRows(rows: AttendanceRecord[]): number {
  return rows.filter((row) => Boolean(row.LoginTime || row.LogoutTime || Number(row.WorkingHours || 0) > 0)).length;
}

export default function ManagerEmployeeDrilldownPage() {
  const params = useParams<{ employeeEmail: string }>();
  const searchParams = useSearchParams();
  const employeeEmail = decodeURIComponent(params.employeeEmail);
  const initialMonth = searchParams.get("month") || new Date().toISOString().slice(0, 7);

  const [month, setMonth] = useState(initialMonth);
  const [statusFilter, setStatusFilter] = useState("all");
  const [activityOnly, setActivityOnly] = useState(false);

  const attendance = useEmployeeMonthlyAttendanceQuery(employeeEmail, month);
  const rows = (attendance.data || []) as AttendanceRecord[];

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (statusFilter !== "all" && row.AttendanceStatus !== statusFilter) {
        return false;
      }

      if (activityOnly) {
        return Boolean(row.LoginTime || row.LogoutTime || Number(row.WorkingHours || 0) > 0);
      }

      return true;
    });
  }, [rows, statusFilter, activityOnly]);

  const statuses = useMemo(() => statusList(rows), [rows]);
  const employeeName = useMemo(() => employeeDisplayName(rows, employeeEmail), [rows, employeeEmail]);
  const totalWorkingHours = useMemo(() => totalHours(filteredRows), [filteredRows]);
  const averageHours = filteredRows.length ? totalWorkingHours / filteredRows.length : 0;

  return (
    <LoginGate>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link className="text-sm font-semibold text-[color:var(--brand)] hover:underline" href="/manager">
              Back to Manager Dashboard
            </Link>
            <h1 className="mt-2 text-3xl font-extrabold">{employeeName}</h1>
            <p className="mt-1 text-[color:var(--muted)]">Employee monthly attendance drilldown for managers.</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <input
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              type="month"
              value={month}
              onChange={(event) => setMonth(event.target.value)}
            />

            <select
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">All Statuses</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>

            <label className="flex items-center gap-2 rounded-lg border border-slate-300/40 px-3 py-2 text-sm">
              <input type="checkbox" checked={activityOnly} onChange={(event) => setActivityOnly(event.target.checked)} />
              Activity only
            </label>
          </div>
        </div>

        <section className="mt-6">
          <CardGrid>
            <StatCard title="Records" value={String(filteredRows.length)} accent="var(--brand)" />
            <StatCard title="Present-like Days" value={String(presentLikeCount(filteredRows))} accent="var(--ok)" />
            <StatCard title="Active Days" value={String(activeRows(filteredRows))} accent="var(--warn)" />
            <StatCard title="Total Hours" value={totalWorkingHours.toFixed(2)} accent="var(--brand-2)" />
            <StatCard title="Average Hours" value={averageHours.toFixed(2)} accent="var(--ok)" />
          </CardGrid>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-300/30 p-4 text-sm text-[color:var(--muted)]">
          Showing {filteredRows.length} of {rows.length} records for {employeeEmail}
        </section>

        <section className="mt-6">
          <AttendanceTable data={filteredRows} />
        </section>
      </main>
    </LoginGate>
  );
}
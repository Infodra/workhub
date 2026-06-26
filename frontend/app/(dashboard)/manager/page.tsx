"use client";

import { useMemo, useState } from "react";

import { authPost } from "@/lib/api";
import { CardGrid, StatCard } from "@/components/card-grid";
import { LoginGate } from "@/components/login-gate";
import { useCurrentAccount, useDashboardQuery, useMonthlyAttendanceQuery } from "@/lib/hooks";
import { AttendanceTable } from "@/components/attendance-table";
import { AttendanceRecord } from "@/types";

function toDateKey(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(0, 10);
  }

  return toLocalDateKey(parsed);
}

function toLocalDateKey(date: Date): string {
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function hasActivity(record: AttendanceRecord): boolean {
  return Boolean(
    record.LoginTime ||
      record.LogoutTime ||
      Number(record.WorkingHours || 0) > 0 ||
      Number(record.MeetingHours || 0) > 0,
  );
}

function startOfWeek(source: Date): Date {
  const date = new Date(source);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday as start of week
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function endOfWeek(source: Date): Date {
  const date = startOfWeek(source);
  date.setDate(date.getDate() + 6);
  date.setHours(23, 59, 59, 999);
  return date;
}

function getRecordDate(record: AttendanceRecord): Date | null {
  const parsed = new Date(record.AttendanceDate);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

export default function ManagerDashboardPage() {
  const account = useCurrentAccount();
  const dashboard = useDashboardQuery();
  const month = new Date().toISOString().slice(0, 7);
  const monthly = useMonthlyAttendanceQuery(month);
  const data = dashboard.data || {};
  const rows = (monthly.data || []) as AttendanceRecord[];

  const [search, setSearch] = useState("");
  const [employeeFilter, setEmployeeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [activityOnly, setActivityOnly] = useState(false);
  const [periodView, setPeriodView] = useState<"weekly" | "monthly">("monthly");

  const employeeOptions = useMemo(() => {
    const labels = Array.from(
      new Set(
        rows
          .map((row) => row.EmployeeName || row.EmployeeEmail || row.Employee || "Unknown")
          .map((value) => String(value)),
      ),
    );
    return labels.sort((a, b) => a.localeCompare(b));
  }, [rows]);

  const statusOptions = useMemo(() => {
    const statuses = Array.from(new Set(rows.map((row) => String(row.AttendanceStatus || "Unknown"))));
    return statuses.sort((a, b) => a.localeCompare(b));
  }, [rows]);

  const filteredRows = useMemo(() => {
    const searchLower = search.trim().toLowerCase();
    const now = new Date();
    const weekStart = startOfWeek(now);
    const weekEnd = endOfWeek(now);
    const weekStartKey = toLocalDateKey(weekStart);
    const weekEndKey = toLocalDateKey(weekEnd);

    return rows.filter((row) => {
      const employee = String(row.EmployeeName || row.EmployeeEmail || row.Employee || "Unknown");
      const employeeLower = employee.toLowerCase();
      const status = String(row.AttendanceStatus || "Unknown");
      const dateKey = toDateKey(row.AttendanceDate);

      if (periodView === "weekly") {
        if (dateKey < weekStartKey || dateKey > weekEndKey) {
          return false;
        }
      }

      if (employeeFilter !== "all" && employee !== employeeFilter) {
        return false;
      }

      if (statusFilter !== "all" && status !== statusFilter) {
        return false;
      }

      if (fromDate && dateKey < fromDate) {
        return false;
      }

      if (toDate && dateKey > toDate) {
        return false;
      }

      if (activityOnly && !hasActivity(row)) {
        return false;
      }

      if (!searchLower) {
        return true;
      }

      return (
        employeeLower.includes(searchLower) ||
        status.toLowerCase().includes(searchLower) ||
        dateKey.includes(searchLower)
      );
    });
  }, [rows, search, employeeFilter, statusFilter, fromDate, toDate, activityOnly, periodView]);

  const periodSummary = useMemo(() => {
    const now = new Date();
    const weekStart = startOfWeek(now);
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

    const weeklyRows = filteredRows.filter((row) => {
      const date = getRecordDate(row);
      return date ? date >= weekStart && date <= now : false;
    });

    const monthlyRows = filteredRows.filter((row) => {
      const date = getRecordDate(row);
      return date ? date >= monthStart && date <= now : false;
    });

    const sumEffort = (list: AttendanceRecord[]) =>
      list.reduce((acc, row) => acc + Number(row.WorkingHours || 0) + Number(row.MeetingHours || 0), 0);

    const countPresentLike = (list: AttendanceRecord[]) =>
      list.filter((row) => ["Present", "Late", "Half Day"].includes(String(row.AttendanceStatus || ""))).length;

    const weekHours = sumEffort(weeklyRows);
    const monthHours = sumEffort(monthlyRows);

    return {
      weeklyRows: weeklyRows.length,
      weeklyHours: weekHours,
      weeklyAvgHours: weeklyRows.length ? weekHours / weeklyRows.length : 0,
      weeklyPresentLike: countPresentLike(weeklyRows),
      monthlyRows: monthlyRows.length,
      monthlyHours: monthHours,
      monthlyAvgHours: monthlyRows.length ? monthHours / monthlyRows.length : 0,
      monthlyPresentLike: countPresentLike(monthlyRows),
    };
  }, [filteredRows]);

  function resetFilters() {
    setSearch("");
    setEmployeeFilter("all");
    setStatusFilter("all");
    setFromDate("");
    setToDate("");
    setActivityOnly(false);
  }

  function employeeDrilldownHref(record: AttendanceRecord): string | undefined {
    const employeeEmail = record.EmployeeEmail || record.Employee;
    if (!employeeEmail) {
      return undefined;
    }
    return `/manager/${encodeURIComponent(employeeEmail)}?month=${month}`;
  }

  async function triggerSync() {
    if (!account) {
      return;
    }

    const now = new Date();
    const targetDate = now.toISOString().slice(0, 10);

    await authPost("/sync", { target_date: targetDate }, account, { timeoutMs: 180000 });
    await dashboard.refetch();
    await monthly.refetch();
  }

  return (
    <LoginGate>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-extrabold">Manager Dashboard</h1>
            <p className="mt-1 text-[color:var(--muted)]">Team attendance overview, late logins, absentees, and trends.</p>
          </div>
          <button
            className="rounded-full border px-4 py-2 text-sm font-semibold"
            onClick={triggerSync}
            type="button"
          >
            Run Sync
          </button>
        </div>

        <section className="mt-6">
          <CardGrid>
            <StatCard title="Present Employees" value={String(data.present_employees || 0)} accent="var(--ok)" />
            <StatCard title="Absent Employees" value={String(data.absent_employees || 0)} accent="var(--danger)" />
            <StatCard title="Late Login" value={String(data.late_login || 0)} accent="var(--warn)" />
            <StatCard title="Attendance %" value={`${String(data.attendance_percentage || 0)}%`} accent="var(--brand)" />
          </CardGrid>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-300/30 p-4">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <button
              className={`rounded-full px-4 py-2 text-sm font-semibold ${periodView === "weekly" ? "bg-[color:var(--brand)] text-white" : "border"}`}
              type="button"
              onClick={() => setPeriodView("weekly")}
            >
              Weekly Records
            </button>
            <button
              className={`rounded-full px-4 py-2 text-sm font-semibold ${periodView === "monthly" ? "bg-[color:var(--brand)] text-white" : "border"}`}
              type="button"
              onClick={() => setPeriodView("monthly")}
            >
              Monthly Records
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            <input
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              type="text"
              placeholder="Search employee/status/date"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />

            <select
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              value={employeeFilter}
              onChange={(event) => setEmployeeFilter(event.target.value)}
            >
              <option value="all">All Employees</option>
              {employeeOptions.map((employee) => (
                <option key={employee} value={employee}>
                  {employee}
                </option>
              ))}
            </select>

            <select
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">All Statuses</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>

            <input
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              type="date"
              value={fromDate}
              onChange={(event) => setFromDate(event.target.value)}
            />

            <input
              className="rounded-lg border border-slate-300/40 bg-transparent px-3 py-2 text-sm"
              type="date"
              value={toDate}
              onChange={(event) => setToDate(event.target.value)}
            />

            <label className="flex items-center gap-2 rounded-lg border border-slate-300/40 px-3 py-2 text-sm">
              <input
                type="checkbox"
                checked={activityOnly}
                onChange={(event) => setActivityOnly(event.target.checked)}
              />
              Activity only
            </label>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="text-[color:var(--muted)]">
              Showing {filteredRows.length} of {rows.length} records in {periodView === "weekly" ? "weekly" : "monthly"} view
            </p>
            <button className="rounded-full border px-3 py-1.5 text-xs font-semibold" type="button" onClick={resetFilters}>
              Clear Filters
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-slate-300/30 p-3">
              <p className="text-xs uppercase tracking-wide text-[color:var(--muted)]">Weekly Summary</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <p>Records: <span className="font-semibold">{periodSummary.weeklyRows}</span></p>
                <p>Present-like: <span className="font-semibold">{periodSummary.weeklyPresentLike}</span></p>
                <p>Total Effort: <span className="font-semibold">{periodSummary.weeklyHours.toFixed(2)}</span></p>
                <p>Avg Effort: <span className="font-semibold">{periodSummary.weeklyAvgHours.toFixed(2)}</span></p>
              </div>
            </div>

            <div className="rounded-xl border border-slate-300/30 p-3">
              <p className="text-xs uppercase tracking-wide text-[color:var(--muted)]">Monthly Summary</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <p>Records: <span className="font-semibold">{periodSummary.monthlyRows}</span></p>
                <p>Present-like: <span className="font-semibold">{periodSummary.monthlyPresentLike}</span></p>
                <p>Total Effort: <span className="font-semibold">{periodSummary.monthlyHours.toFixed(2)}</span></p>
                <p>Avg Effort: <span className="font-semibold">{periodSummary.monthlyAvgHours.toFixed(2)}</span></p>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6">
          <AttendanceTable data={filteredRows} employeeHref={employeeDrilldownHref} />
        </section>
      </main>
    </LoginGate>
  );
}

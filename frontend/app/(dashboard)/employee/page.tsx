"use client";

import { CardGrid, StatCard } from "@/components/card-grid";
import { LoginGate } from "@/components/login-gate";
import { useDashboardQuery, useMonthlyAttendanceQuery } from "@/lib/hooks";
import { AttendanceChart } from "@/components/attendance-chart";

export default function EmployeeDashboardPage() {
  const dashboard = useDashboardQuery();
  const month = new Date().toISOString().slice(0, 7);
  const monthData = useMonthlyAttendanceQuery(month);
  const data = dashboard.data || {};

  return (
    <LoginGate>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-extrabold">Employee Dashboard</h1>
        <p className="mt-1 text-[color:var(--muted)]">Attendance, working hours, meeting time, leave, holidays, and announcements.</p>

        <section className="mt-6">
          <CardGrid>
            <StatCard title="Today's Login" value={String(data.todays_login || "-")} />
            <StatCard title="Today's Logout" value={String(data.todays_logout || "-")} />
            <StatCard title="Working Hours" value={String(data.working_hours || 0)} />
            <StatCard title="Meeting Hours" value={String(data.meeting_hours || 0)} />
            <StatCard title="Attendance Status" value={String(data.attendance_status || "-")} accent="var(--ok)" />
            <StatCard title="Monthly Attendance" value={String(data.monthly_attendance || 0)} accent="var(--brand)" />
            <StatCard title="Leave Balance" value={String(data.leave_balance || 0)} accent="var(--warn)" />
            <StatCard title="Upcoming Holidays" value={String((data.upcoming_holidays as unknown[] | undefined)?.length || 0)} />
          </CardGrid>
        </section>

        <section className="mt-6">
          <AttendanceChart data={monthData.data || []} />
        </section>
      </main>
    </LoginGate>
  );
}

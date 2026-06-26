"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AttendanceRecord } from "@/types";

function dayLabel(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(8, 10);
  }
  return String(parsed.getDate()).padStart(2, "0");
}

export function AttendanceChart({ data }: { data: AttendanceRecord[] }) {
  const chartData = data.map((item) => ({
    day: dayLabel(item.AttendanceDate),
    working: Number(item.WorkingHours || 0),
    meeting: Number(item.MeetingHours || 0),
  }));

  return (
    <div className="card rounded-2xl p-5 shadow-sm">
      <h3 className="text-lg font-bold">Monthly Hours Trend</h3>
      <div className="mt-4 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="day" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="working" fill="var(--brand)" radius={[6, 6, 0, 0]} />
            <Bar dataKey="meeting" fill="var(--brand-2)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

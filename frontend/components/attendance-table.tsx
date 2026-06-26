import Link from "next/link";

import { AttendanceRecord } from "@/types";

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

function formatTime(value?: string): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

function employeeLabel(record: AttendanceRecord): string {
  return record.EmployeeName || record.EmployeeEmail || record.Employee || "Unknown";
}

function totalHours(record: AttendanceRecord): string {
  const working = Number(record.WorkingHours || 0);
  const meeting = Number(record.MeetingHours || 0);
  return (working + meeting).toFixed(2);
}

function effectiveLogout(record: AttendanceRecord): string | undefined {
  if (record.LogoutTime) {
    return record.LogoutTime;
  }

  if (record.LastActivity && record.LastActivity !== record.LoginTime) {
    return record.LastActivity;
  }

  return undefined;
}

function assetBadge(record: AttendanceRecord): React.ReactNode {
  if (!record.AssetType) return null;
  const isCompany = record.AssetType?.includes("Company");
  const bgColor = isCompany ? "bg-blue-100 text-blue-800" : "bg-gray-100 text-gray-700";
  return (
    <span className={`ml-2 inline-block rounded px-2 py-1 text-xs font-medium ${bgColor}`}>
      {record.AssetType}
    </span>
  );
}

export function AttendanceTable({
  data,
  employeeHref,
}: {
  data: AttendanceRecord[];
  employeeHref?: (record: AttendanceRecord) => string | undefined;
}) {
  return (
    <div className="card overflow-x-auto rounded-2xl p-5 shadow-sm">
      <h3 className="text-lg font-bold">Attendance Records</h3>
      <table className="mt-4 min-w-full text-sm">
        <thead>
          <tr className="text-left text-[color:var(--muted)]">
            <th className="py-2 pr-3">Employee</th>
            <th className="py-2 pr-3">Date</th>
            <th className="py-2 pr-3">Login</th>
            <th className="py-2 pr-3">Logout</th>
            <th className="py-2 pr-3">Working</th>
            <th className="py-2 pr-3">Meeting</th>
            <th className="py-2 pr-3">Total Effort</th>
            <th className="py-2 pr-3">Device</th>
            <th className="py-2 pr-3">Status</th>
            <th className="py-2 pr-3">Reason</th>
          </tr>
        </thead>
        <tbody>
          {data.map((record, index) => (
            <tr
              key={record.id ?? `${record.AttendanceDate}-${record.AttendanceStatus}-${index}`}
              className="border-t border-slate-300/30"
            >
              <td className="py-2 pr-3">
                <div className="flex items-center">
                  {employeeHref?.(record) ? (
                    <Link className="font-medium text-[color:var(--brand)] hover:underline" href={employeeHref(record)!}>
                      {employeeLabel(record)}
                    </Link>
                  ) : (
                    employeeLabel(record)
                  )}
                  {assetBadge(record)}
                </div>
              </td>
              <td className="py-2 pr-3">{formatDate(record.AttendanceDate)}</td>
              <td className="py-2 pr-3">{formatTime(record.LoginTime)}</td>
              <td className="py-2 pr-3">{formatTime(effectiveLogout(record))}</td>
              <td className="py-2 pr-3">{record.WorkingHours}</td>
              <td className="py-2 pr-3">{record.MeetingHours}</td>
              <td className="py-2 pr-3">{totalHours(record)}</td>
              <td className="py-2 pr-3">{assetBadge(record) ?? <span className="text-xs text-gray-400">Personal</span>}</td>
              <td className="py-2 pr-3">{record.AttendanceStatus}</td>
              <td className="py-2 pr-3">{record.Remarks || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

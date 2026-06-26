import { PropsWithChildren } from "react";

export function CardGrid({ children }: PropsWithChildren) {
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

export function StatCard({ title, value, accent }: { title: string; value: string; accent?: string }) {
  return (
    <article className="card rounded-2xl p-5 shadow-sm">
      <p className="text-sm font-semibold text-[color:var(--muted)]">{title}</p>
      <p className="mt-2 text-3xl font-extrabold" style={{ color: accent || "var(--text)" }}>
        {value}
      </p>
    </article>
  );
}

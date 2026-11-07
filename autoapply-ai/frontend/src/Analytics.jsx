import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Section, STATUS_LABEL, STATUS_STYLE } from "./ui.jsx";

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  );
}

function Bars({ rows, tone = "bg-blue-600" }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.every((r) => r.value === 0)) return <p className="text-sm text-slate-500">Nothing to show yet.</p>;
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-3 text-sm">
          <div className="w-28 shrink-0 truncate text-slate-600">{r.label}</div>
          <div className="h-3 flex-1 rounded bg-slate-100">
            <div className={`h-3 rounded ${r.tone || tone}`} style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
          <div className="w-8 text-right font-medium text-slate-800">{r.value}</div>
        </div>
      ))}
    </div>
  );
}

export default function Analytics({ refreshKey }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api("/stats").then(setStats).catch(() => {});
  }, [refreshKey]);

  if (!stats) return <p className="py-6 text-sm text-slate-500">Loading analytics...</p>;

  const submitted = (stats.by_status.submitted || 0) + (stats.by_status.dry_run || 0);
  const statusRows = Object.entries(stats.by_status).map(([k, v]) => ({
    label: STATUS_LABEL[k] || k,
    value: v,
    tone: STATUS_STYLE[k]?.includes("emerald") ? "bg-emerald-500" : STATUS_STYLE[k]?.includes("red") ? "bg-red-500" : "bg-blue-600",
  }));

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 py-6 md:grid-cols-4">
        <Stat label="Jobs ingested" value={stats.jobs_total} />
        <Stat label="Average match" value={stats.jobs_scored ? stats.avg_match : "n/a"} />
        <Stat label="Applications" value={stats.applications_total} />
        <Stat label="Submitted or dry run" value={submitted} />
      </div>
      <div className="grid gap-8 md:grid-cols-2">
        <Section title="Applications by status">
          <Bars rows={statusRows} />
        </Section>
        <Section title="Match score distribution">
          <Bars
            rows={[
              { label: "70 and above", value: stats.score_buckets["70+"], tone: "bg-emerald-500" },
              { label: "40 to 69", value: stats.score_buckets["40-69"], tone: "bg-amber-500" },
              { label: "Under 40", value: stats.score_buckets["under 40"], tone: "bg-slate-400" },
            ]}
          />
        </Section>
        <Section title="Applications, last 14 days">
          <Bars rows={stats.applications_by_day.map((d) => ({ label: d.date.slice(5), value: d.count }))} />
        </Section>
        <Section title="Most common missing skills">
          <Bars rows={stats.top_missing_skills.map((s) => ({ label: s.skill, value: s.count, tone: "bg-amber-500" }))} />
        </Section>
        <Section title="Jobs by company">
          <Bars rows={Object.entries(stats.companies).map(([k, v]) => ({ label: k, value: v }))} />
        </Section>
      </div>
    </div>
  );
}

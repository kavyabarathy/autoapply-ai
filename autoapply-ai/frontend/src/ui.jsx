export const field =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600";
export const primary =
  "rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50";
export const secondary =
  "rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50";
export const success =
  "rounded-md border border-emerald-700 px-4 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-50 disabled:opacity-50";

export const STATUS_STYLE = {
  queued: "bg-slate-100 text-slate-700",
  preparing: "bg-blue-100 text-blue-800",
  pending_review: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  submitting: "bg-blue-100 text-blue-800",
  submitted: "bg-emerald-100 text-emerald-800",
  dry_run: "bg-teal-100 text-teal-800",
  failed: "bg-red-100 text-red-800",
  rejected: "bg-slate-100 text-slate-500",
};

export const STATUS_LABEL = {
  queued: "Queued",
  preparing: "Preparing",
  pending_review: "Needs review",
  approved: "Approved",
  submitting: "Submitting",
  submitted: "Submitted",
  dry_run: "Dry run",
  failed: "Failed",
  rejected: "Skipped",
};

export const ACTIVE = ["queued", "preparing", "approved", "submitting"];

export function Section({ title, children }) {
  return (
    <section className="border-t border-slate-200 py-6">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

export function ScoreBadge({ score }) {
  if (score === undefined || score === null) return <span className="text-slate-400">Not scored</span>;
  const tone =
    score >= 70 ? "bg-emerald-100 text-emerald-800" : score >= 40 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-2 py-0.5 text-sm font-semibold ${tone}`}>{score}</span>;
}

export function StatusBadge({ status }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] || STATUS_STYLE.queued}`}>
      {STATUS_LABEL[status] || status}
    </span>
  );
}

import { useEffect, useState } from "react";
import { api, downloadBlob, fetchBlob, json } from "./api.js";
import { field, primary, secondary, Section, StatusBadge } from "./ui.jsx";

function Question({ q, value, onChange, disabled }) {
  const label = (
    <label className="mb-1 block text-sm font-medium text-slate-800">
      {q.label}
      {q.required && <span className="ml-1 text-red-600">*</span>}
    </label>
  );
  if (q.kind === "textarea") {
    return (
      <div>
        {label}
        <textarea className={field} rows={4} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
      </div>
    );
  }
  if (q.kind === "select" || q.kind === "radio") {
    return (
      <div>
        {label}
        <select className={field} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select...</option>
          {q.options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      </div>
    );
  }
  if (q.kind === "checkbox") {
    const chosen = value ? value.split(" | ") : [];
    const toggle = (o) => onChange((chosen.includes(o) ? chosen.filter((c) => c !== o) : [...chosen, o]).join(" | "));
    return (
      <div>
        {label}
        <div className="flex flex-wrap gap-3 text-sm">
          {q.options.map((o) => (
            <label key={o} className="flex items-center gap-1">
              <input type="checkbox" disabled={disabled} checked={chosen.includes(o)} onChange={() => toggle(o)} />
              {o}
            </label>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div>
      {label}
      <input className={field} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function Detail({ id, reload, onClose }) {
  const [app, setApp] = useState(null);
  const [answers, setAnswers] = useState({});
  const [cover, setCover] = useState("");
  const [shot, setShot] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const data = await api(`/applications/${id}`);
    setApp(data);
    setAnswers(Object.fromEntries((data.questions || []).map((q) => [q.id, q.answer || ""])));
    setCover(data.cover_note || "");
    const kind = data.files?.result ? "result" : data.files?.review ? "review" : null;
    if (kind) {
      const blob = await fetchBlob(`/applications/${id}/files/${kind}`);
      setShot((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(blob);
      });
    } else {
      setShot("");
    }
  };

  useEffect(() => {
    load().catch((e) => setNote(e.message));
  }, [id]);

  useEffect(() => {
    if (app && ["queued", "preparing", "approved", "submitting"].includes(app.status)) {
      const t = setTimeout(() => load().catch(() => {}), 3000);
      return () => clearTimeout(t);
    }
  }, [app]);

  if (!app) return <p className="text-sm text-slate-500">{note || "Loading..."}</p>;

  const review = app.status === "pending_review";
  const act = async (fn) => {
    setBusy(true);
    setNote("");
    try {
      await fn();
      await load();
      await reload();
    } catch (e) {
      setNote(e.message);
    } finally {
      setBusy(false);
    }
  };

  const save = () => api(`/applications/${id}/review`, json("PUT", { answers, cover_note: cover }));
  const approve = () =>
    act(async () => {
      if (!window.confirm(`Approve this application to ${app.company}? The form will be submitted if live submission is enabled.`)) return;
      await save();
      await api(`/applications/${id}/approve`, { method: "POST" });
    });

  return (
    <div className="rounded-lg border border-slate-200 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{app.title}</h3>
          <p className="text-sm text-slate-500">{app.company}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={app.status} />
          <button className="text-sm text-slate-500 hover:underline" onClick={onClose}>Close</button>
        </div>
      </div>

      {app.error && <p className="mt-3 rounded bg-red-50 p-3 text-sm text-red-800">{app.error}</p>}
      {app.status === "dry_run" && (
        <p className="mt-3 rounded bg-teal-50 p-3 text-sm text-teal-800">
          Dry run complete. The form was filled but not sent because SUBMIT_ENABLED is false.
        </p>
      )}
      {note && <p className="mt-3 text-sm text-red-700">{note}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        {app.files?.docx && <button className={secondary} onClick={() => downloadBlob(`/applications/${id}/files/docx`, "resume.docx")}>Tailored DOCX</button>}
        {app.files?.pdf && <button className={secondary} onClick={() => downloadBlob(`/applications/${id}/files/pdf`, "resume.pdf")}>Tailored PDF</button>}
        <a className={secondary} href={app.url} target="_blank" rel="noreferrer">Open posting</a>
      </div>

      {shot && (
        <div className="mt-4">
          <p className="mb-1 text-sm font-medium text-slate-700">Pre-filled form</p>
          <div className="max-h-96 overflow-auto rounded border border-slate-200">
            <img src={shot} alt="Pre-filled application form" className="w-full" />
          </div>
        </div>
      )}

      {app.tailored?.summary && (
        <div className="mt-4 text-sm">
          <p className="font-medium text-slate-700">Tailored summary</p>
          <p className="text-slate-600">{app.tailored.summary}</p>
        </div>
      )}

      {(app.questions?.length > 0 || review) && (
        <div className="mt-4 space-y-3">
          <p className="text-sm font-medium text-slate-700">Screening questions and notes</p>
          {(app.questions || []).map((q) => (
            <Question key={q.id} q={q} value={answers[q.id] || ""} disabled={!review} onChange={(v) => setAnswers({ ...answers, [q.id]: v })} />
          ))}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-800">Additional information</label>
            <textarea className={field} rows={3} value={cover} disabled={!review} onChange={(e) => setCover(e.target.value)} />
          </div>
        </div>
      )}

      {review && (
        <div className="mt-4 flex gap-3">
          <button className={primary} disabled={busy} onClick={approve}>Approve and submit</button>
          <button className={secondary} disabled={busy} onClick={() => act(save)}>Save edits</button>
          <button className={secondary} disabled={busy} onClick={() => act(() => api(`/applications/${id}/reject`, { method: "POST" }))}>Skip</button>
        </div>
      )}
      {app.status === "failed" && (
        <div className="mt-4 flex gap-3">
          <button className={primary} disabled={busy} onClick={() => act(() => api(`/applications/${id}/retry`, { method: "POST" }))}>Retry</button>
          <button className={secondary} disabled={busy} onClick={() => act(() => api(`/applications/${id}/reject`, { method: "POST" }))}>Skip</button>
        </div>
      )}

      <div className="mt-5">
        <p className="mb-1 text-sm font-medium text-slate-700">Activity log</p>
        <ul className="space-y-1 text-sm text-slate-600">
          {app.logs.map((l) => (
            <li key={l.id}>
              <span className="text-slate-400">{new Date(l.at).toLocaleTimeString()}</span> {l.detail || l.event}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function Applications({ applications, reload, focusId, setFocusId }) {
  return (
    <Section title="Applications">
      {applications.length === 0 ? (
        <p className="text-sm text-slate-500">No applications yet. Use Apply on a job in the Jobs tab.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-300 text-slate-600">
              <tr>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Match</th>
                <th className="py-2 pr-4">Started</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {applications.map((a) => (
                <tr key={a.id} className={`border-b border-slate-100 ${focusId === a.id ? "bg-blue-50" : ""}`}>
                  <td className="py-3 pr-4"><StatusBadge status={a.status} /></td>
                  <td className="py-3 pr-4">
                    <div className="font-medium text-slate-800">{a.title}</div>
                    <div className="text-slate-500">{a.company}</div>
                  </td>
                  <td className="py-3 pr-4 text-slate-600">{a.match_score ?? ""}</td>
                  <td className="py-3 pr-4 text-slate-600">{new Date(a.created_at).toLocaleString()}</td>
                  <td className="py-3 text-right">
                    <button className="text-blue-700 hover:underline" onClick={() => setFocusId(a.id)}>
                      {a.status === "pending_review" ? "Review" : "Details"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {focusId && (
        <div className="mt-6">
          <Detail key={focusId} id={focusId} reload={reload} onClose={() => setFocusId(null)} />
        </div>
      )}
    </Section>
  );
}

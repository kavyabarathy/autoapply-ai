import { useEffect, useState } from "react";

const API = "http://localhost:8000";

async function api(path, options) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const field =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600";
const primary =
  "rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50";

function Section({ title, children }) {
  return (
    <section className="border-t border-slate-200 py-6">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

function ScoreBadge({ score }) {
  if (score === undefined) return <span className="text-slate-400">Not scored</span>;
  const tone =
    score >= 70 ? "bg-emerald-100 text-emerald-800" : score >= 40 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-2 py-0.5 text-sm font-semibold ${tone}`}>{score}</span>;
}

export default function App() {
  const [profile, setProfile] = useState({ name: "", target_titles: "", locations: "", background: "" });
  const [resume, setResume] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const loadJobs = () => api("/jobs").then(setJobs).catch((e) => setMessage(e.message));

  useEffect(() => {
    api("/profile")
      .then((p) =>
        setProfile({
          name: p.name || "",
          target_titles: (p.target_titles || []).join(", "),
          locations: (p.locations || []).join(", "),
          background: p.background || "",
        })
      )
      .catch(() => {});
    api("/resume").then(setResume).catch(() => {});
    loadJobs();
  }, []);

  const run = async (label, fn) => {
    setBusy(true);
    setMessage(label);
    try {
      await fn();
      setMessage("Done.");
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  const split = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const saveProfile = () =>
    run("Saving profile...", () =>
      api("/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: profile.name,
          target_titles: split(profile.target_titles),
          locations: split(profile.locations),
          background: profile.background,
        }),
      })
    );

  const uploadResume = (file) =>
    run("Parsing resume...", async () => {
      const form = new FormData();
      form.append("file", file);
      const data = await api("/resume", { method: "POST", body: form });
      setResume(data);
    });

  const scrape = () =>
    run(`Scraping ${company}...`, async () => {
      await api("/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company, limit: 10 }),
      });
      await loadJobs();
    });

  const scoreAll = () =>
    run("Scoring jobs with the LLM...", async () => {
      await api("/match-all?limit=10", { method: "POST" });
      await loadJobs();
    });

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 text-slate-800">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">AutoApply AI</h1>
        <p className="mt-1 text-slate-600">Find openings, score your fit, and review before anything is submitted.</p>
      </header>

      <Section title="Your profile">
        <div className="grid gap-3 md:grid-cols-2">
          <input className={field} placeholder="Name" value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
          <input className={field} placeholder="Target titles (comma separated)" value={profile.target_titles} onChange={(e) => setProfile({ ...profile, target_titles: e.target.value })} />
          <input className={field} placeholder="Locations (comma separated)" value={profile.locations} onChange={(e) => setProfile({ ...profile, locations: e.target.value })} />
          <textarea className={`${field} md:col-span-2`} rows={3} placeholder="Short background" value={profile.background} onChange={(e) => setProfile({ ...profile, background: e.target.value })} />
        </div>
        <button className={`${primary} mt-3`} disabled={busy} onClick={saveProfile}>Save profile</button>
      </Section>

      <Section title="Master resume">
        <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => e.target.files[0] && uploadResume(e.target.files[0])} className="text-sm" />
        {resume && (
          <div className="mt-3 text-sm">
            <p className="text-slate-700">Uploaded: {resume.filename}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(resume.keywords || []).map((k) => (
                <span key={k} className="rounded-full bg-blue-50 px-3 py-1 text-blue-800">{k}</span>
              ))}
            </div>
          </div>
        )}
      </Section>

      <Section title="Job queue">
        <div className="mb-4 flex flex-wrap gap-3">
          <input className={`${field} max-w-xs`} placeholder="Lever company, e.g. palantir" value={company} onChange={(e) => setCompany(e.target.value)} />
          <button className={primary} disabled={busy || !company} onClick={scrape}>Scrape jobs</button>
          <button className="rounded-md border border-emerald-700 px-4 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-50 disabled:opacity-50" disabled={busy} onClick={scoreAll}>
            Score unscored jobs
          </button>
        </div>
        {message && <p className="mb-3 text-sm text-slate-600">{message}</p>}
        {jobs.length === 0 ? (
          <p className="text-sm text-slate-500">No jobs yet. Enter a company above and scrape its open roles.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-300 text-slate-600">
                <tr>
                  <th className="py-2 pr-4">Match</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Location</th>
                  <th className="py-2">Why</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id} className="border-b border-slate-100 align-top">
                    <td className="py-3 pr-4"><ScoreBadge score={j.match_score} /></td>
                    <td className="py-3 pr-4">
                      <a href={j.url} target="_blank" rel="noreferrer" className="font-medium text-blue-700 hover:underline">{j.title}</a>
                      <div className="text-slate-500">{j.company}</div>
                    </td>
                    <td className="py-3 pr-4 text-slate-600">{j.location}</td>
                    <td className="py-3 text-slate-600">{j.match_reason || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}

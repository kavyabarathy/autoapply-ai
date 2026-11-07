import { useEffect, useState } from "react";
import { api, downloadBlob, json } from "./api.js";
import Analytics from "./Analytics.jsx";
import Applications from "./Applications.jsx";
import { ACTIVE, field, primary, ScoreBadge, secondary, Section, StatusBadge, success } from "./ui.jsx";

const TABS = [
  ["dashboard", "Dashboard"],
  ["jobs", "Jobs"],
  ["applications", "Applications"],
  ["profile", "Profile"],
];

const EMPTY_PROFILE = {
  name: "",
  email: "",
  phone: "",
  linkedin: "",
  github: "",
  website: "",
  current_company: "",
  target_titles: "",
  locations: "",
  companies: "",
  background: "",
};

async function waitForTask(id) {
  for (let i = 0; i < 120; i++) {
    const task = await api(`/tasks/${id}`);
    if (task.state === "SUCCESS") return task.result;
    if (task.state === "FAILURE") throw new Error(task.result || "Task failed");
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error("The task is taking too long. Check that the Celery worker is running.");
}

export default function App({ onLogout }) {
  const [tab, setTab] = useState("dashboard");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [resume, setResume] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [applications, setApplications] = useState([]);
  const [focusId, setFocusId] = useState(null);
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const loadJobs = () => api("/jobs").then(setJobs).catch((e) => setMessage(e.message));
  const loadApplications = () => api("/applications").then(setApplications).catch(() => {});

  useEffect(() => {
    api("/profile")
      .then((p) =>
        setProfile({
          ...EMPTY_PROFILE,
          ...Object.fromEntries(Object.keys(EMPTY_PROFILE).map((k) => [k, p[k] || ""])),
          target_titles: (p.target_titles || []).join(", "),
          locations: (p.locations || []).join(", "),
          companies: (p.companies || []).join(", "),
        })
      )
      .catch(() => {});
    api("/resume").then(setResume).catch(() => {});
    loadJobs();
    loadApplications();
  }, []);

  useEffect(() => {
    if (!applications.some((a) => ACTIVE.includes(a.status))) return;
    const timer = setInterval(loadApplications, 3000);
    return () => clearInterval(timer);
  }, [applications]);

  const run = async (label, fn) => {
    setBusy(true);
    setMessage(label);
    try {
      const out = await fn();
      setMessage(typeof out === "string" ? out : "Done.");
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  const split = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const saveProfile = () =>
    run("Saving profile...", () =>
      api(
        "/profile",
        json("PUT", {
          ...profile,
          target_titles: split(profile.target_titles),
          locations: split(profile.locations),
          companies: split(profile.companies),
        })
      )
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
      await api("/scrape", json("POST", { company, limit: 10 }));
      await loadJobs();
    });

  const queueScrape = () =>
    run(`Queued ${company}. Waiting for the worker...`, async () => {
      const { task_id } = await api("/scrape/async", json("POST", { company, limit: 10 }));
      const result = await waitForTask(task_id);
      await loadJobs();
      return `Saved ${result.saved} jobs.`;
    });

  const ingest = () =>
    run("Ingesting your watchlist...", async () => {
      const { task_id } = await api("/ingest", { method: "POST" });
      const result = await waitForTask(task_id);
      await loadJobs();
      return result.errors?.length ? `Saved ${result.saved} jobs. ${result.errors.join(" ")}` : `Saved ${result.saved} jobs.`;
    });

  const scoreAll = () =>
    run("Scoring jobs with the LLM...", async () => {
      await api("/match-all?limit=10", { method: "POST" });
      await loadJobs();
    });

  const applyTo = (job) =>
    run(`Queuing ${job.title}...`, async () => {
      const created = await api(`/jobs/${job.id}/apply`, { method: "POST" });
      await loadApplications();
      setFocusId(created.id);
      return "Queued. The form is being prepared in the background.";
    });

  const applyTop = () =>
    run("Queuing your best matches...", async () => {
      const { queued } = await api("/apply-top?min_score=70&limit=5", { method: "POST" });
      await loadApplications();
      return `Queued ${queued} applications.`;
    });

  const exportResume = (job, format) =>
    run("Tailoring your resume...", async () => {
      await downloadBlob(`/jobs/${job.id}/resume?format=${format}`, `${job.company}-resume.${format}`, { method: "POST" });
    });

  const applicationFor = (jobId) => applications.find((a) => a.job_id === jobId && a.status !== "rejected");
  const review = (id) => {
    setFocusId(id);
    setTab("applications");
  };
  const input = (key, placeholder, extra = "") => (
    <input className={`${field} ${extra}`} placeholder={placeholder} value={profile[key]} onChange={(e) => setProfile({ ...profile, [key]: e.target.value })} />
  );
  const needsReview = applications.filter((a) => a.status === "pending_review").length;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 text-slate-800">
      <header className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">AutoApply AI</h1>
          <p className="mt-1 text-slate-600">Find openings, score your fit, and review before anything is submitted.</p>
        </div>
        <button className="text-sm text-slate-500 hover:underline" onClick={onLogout}>Sign out</button>
      </header>

      <nav className="flex gap-1 border-b border-slate-200">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium ${tab === key ? "border-b-2 border-blue-700 text-blue-800" : "text-slate-600 hover:text-slate-900"}`}
          >
            {label}
            {key === "applications" && needsReview > 0 && (
              <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">{needsReview}</span>
            )}
          </button>
        ))}
      </nav>

      {tab === "dashboard" && <Analytics refreshKey={applications.map((a) => a.status).join() + jobs.length} />}

      {tab === "profile" && (
        <>
          <Section title="Your profile">
            <div className="grid gap-3 md:grid-cols-2">
              {input("name", "Name")}
              {input("email", "Application email")}
              {input("phone", "Phone")}
              {input("current_company", "Current company")}
              {input("linkedin", "LinkedIn URL")}
              {input("github", "GitHub URL")}
              {input("website", "Portfolio or website URL")}
              {input("target_titles", "Target titles (comma separated)")}
              {input("locations", "Locations (comma separated)")}
              {input("companies", "Watchlist: Lever companies (comma separated)")}
              <textarea className={`${field} md:col-span-2`} rows={3} placeholder="Short background" value={profile.background} onChange={(e) => setProfile({ ...profile, background: e.target.value })} />
            </div>
            <button className={`${primary} mt-3`} disabled={busy} onClick={saveProfile}>Save profile</button>
            {message && tab === "profile" && <p className="mt-3 text-sm text-slate-600">{message}</p>}
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
        </>
      )}

      {tab === "jobs" && (
        <Section title="Job queue">
          <div className="mb-4 flex flex-wrap gap-3">
            <input className={`${field} max-w-xs`} placeholder="Lever company, e.g. palantir" value={company} onChange={(e) => setCompany(e.target.value)} />
            <button className={primary} disabled={busy || !company} onClick={scrape}>Scrape jobs</button>
            <button className={secondary} disabled={busy || !company} onClick={queueScrape}>Queue scrape</button>
            <button className={secondary} disabled={busy} onClick={ingest}>Ingest watchlist</button>
            <button className={success} disabled={busy} onClick={scoreAll}>Score unscored jobs</button>
            <button className={success} disabled={busy} onClick={applyTop}>Apply to top matches</button>
          </div>
          {message && tab === "jobs" && <p className="mb-3 text-sm text-slate-600">{message}</p>}
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
                    <th className="py-2 pr-4">Why</th>
                    <th className="py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => {
                    const application = applicationFor(j.id);
                    return (
                      <tr key={j.id} className="border-b border-slate-100 align-top">
                        <td className="py-3 pr-4"><ScoreBadge score={j.match_score} /></td>
                        <td className="py-3 pr-4">
                          <a href={j.url} target="_blank" rel="noreferrer" className="font-medium text-blue-700 hover:underline">{j.title}</a>
                          <div className="text-slate-500">{j.company}</div>
                        </td>
                        <td className="py-3 pr-4 text-slate-600">{j.location}</td>
                        <td className="py-3 pr-4 text-slate-600">{j.match_reason || ""}</td>
                        <td className="py-3">
                          <div className="flex flex-col items-start gap-1">
                            {application ? (
                              <button onClick={() => review(application.id)}><StatusBadge status={application.status} /></button>
                            ) : (
                              <button className="text-blue-700 hover:underline" disabled={busy} onClick={() => applyTo(j)}>Apply</button>
                            )}
                            <span className="text-xs text-slate-500">
                              Resume:{" "}
                              <button className="text-blue-700 hover:underline" disabled={busy} onClick={() => exportResume(j, "docx")}>DOCX</button>{" "}
                              <button className="text-blue-700 hover:underline" disabled={busy} onClick={() => exportResume(j, "pdf")}>PDF</button>
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}

      {tab === "applications" && (
        <Applications applications={applications} reload={loadApplications} focusId={focusId} setFocusId={setFocusId} />
      )}
    </div>
  );
}

import { useState } from "react";
import { api, json, setToken } from "./api.js";
import { field, primary } from "./ui.jsx";

export default function Auth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api(`/auth/${mode}`, json("POST", { email, password }));
      setToken(data.token);
      onAuth();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto mt-24 max-w-sm px-6 text-slate-800">
      <h1 className="text-3xl font-bold text-slate-900">AutoApply AI</h1>
      <p className="mt-1 text-slate-600">{mode === "login" ? "Sign in to your account." : "Create your account."}</p>
      <form onSubmit={submit} className="mt-6 space-y-3">
        <input className={field} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className={field} type="password" placeholder="Password (8+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className={`${primary} w-full`} disabled={busy}>{mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
      <button className="mt-4 text-sm text-blue-700 hover:underline" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
        {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
      </button>
    </div>
  );
}

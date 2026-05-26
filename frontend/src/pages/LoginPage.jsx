import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { expectedEmail, isAuthed, setEmail } from "../auth.js";

export default function LoginPage() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);

  // Already signed in? Skip the form.
  useEffect(() => {
    if (isAuthed()) navigate("/batches", { replace: true });
  }, [navigate]);

  function handleSubmit(e) {
    e.preventDefault();
    const entered = value.trim().toLowerCase();
    if (!entered) {
      setError("Enter your analyst email.");
      return;
    }
    if (entered !== expectedEmail()) {
      setError("That email isn't on the analyst list for this client.");
      return;
    }
    setEmail(entered);
    navigate("/batches", { replace: true });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 px-4">
      <div className="w-full max-w-sm">
        <Brand />
        <div className="mt-6 rounded-xl border border-stone-200 bg-white shadow-sm p-6">
          <h1 className="text-lg font-semibold tracking-tight text-stone-900">
            Analyst sign-in
          </h1>
          <p className="mt-1 text-xs text-stone-500 leading-snug">
            Enter the email assigned to you for this client. The review surface
            is locked until we know who's making the decisions.
          </p>
          <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-stone-500">
                analyst email
              </span>
              <input
                type="email"
                autoFocus
                autoComplete="email"
                spellCheck={false}
                placeholder="analyst@example.com"
                value={value}
                onChange={(e) => { setValue(e.target.value); setError(null); }}
                className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-stone-900 focus:border-stone-900"
              />
            </label>
            {error && (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
                {error}
              </div>
            )}
            <button
              type="submit"
              className="mt-1 rounded-md bg-stone-900 px-3 py-2 text-sm font-medium text-stone-50 hover:bg-stone-700 transition-colors"
            >
              Continue →
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center justify-center gap-2.5 text-stone-900">
      <svg width="22" height="22" viewBox="0 0 20 20" aria-hidden="true">
        <rect x="2"  y="11" width="3" height="7"  rx="0.5" fill="currentColor" />
        <rect x="8.5" y="6"  width="3" height="12" rx="0.5" fill="currentColor" />
        <rect x="15" y="3"  width="3" height="15" rx="0.5" fill="currentColor" />
      </svg>
      <div className="leading-tight text-left">
        <div className="text-base font-semibold tracking-tight">In-Data</div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-stone-500">
          carbon activity ingest
        </div>
      </div>
    </div>
  );
}

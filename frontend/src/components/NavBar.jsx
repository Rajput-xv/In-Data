import { NavLink, useNavigate } from "react-router-dom";

import { clearEmail, getEmail } from "../auth.js";

const linkClass = ({ isActive }) =>
  [
    "px-3 py-1.5 text-sm rounded-md transition-colors",
    isActive
      ? "bg-stone-900 text-stone-50"
      : "text-stone-600 hover:text-stone-900 hover:bg-stone-100",
  ].join(" ");

export default function NavBar() {
  const navigate = useNavigate();
  const email = getEmail();

  function signOut() {
    clearEmail();
    navigate("/", { replace: true });
  }

  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto max-w-7xl flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-7">
          <Brand />
          <nav className="flex items-center gap-1">
            <NavLink to="/batches" className={linkClass}>Batches</NavLink>
            <NavLink to="/review" className={linkClass}>Review</NavLink>
            <NavLink to="/upload" className={linkClass}>Upload</NavLink>
          </nav>
        </div>
        <AnalystPill email={email} onSignOut={signOut} />
      </div>
    </header>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      {/* Three bars = three sources. */}
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
        <rect x="2"  y="11" width="3" height="7"  rx="0.5" fill="currentColor" className="text-stone-900" />
        <rect x="8.5" y="6"  width="3" height="12" rx="0.5" fill="currentColor" className="text-stone-900" />
        <rect x="15" y="3"  width="3" height="15" rx="0.5" fill="currentColor" className="text-stone-900" />
      </svg>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight">In-Data</div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-stone-500">
          carbon activity ingest
        </div>
      </div>
    </div>
  );
}

function AnalystPill({ email, onSignOut }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-stone-200 bg-stone-50 pl-3 pr-1.5 py-1">
      <span className="relative flex h-2 w-2">
        <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60"></span>
        <span className="relative rounded-full h-2 w-2 bg-emerald-500"></span>
      </span>
      <span className="text-[11px] text-stone-500 font-mono">analyst</span>
      <span className="text-[12px] text-stone-800 font-mono">{email}</span>
      <button
        onClick={onSignOut}
        title="Sign out"
        className="ml-1 rounded-full px-1.5 py-0.5 text-[11px] text-stone-500 hover:bg-stone-200 hover:text-stone-800"
      >
        ✕
      </button>
    </div>
  );
}

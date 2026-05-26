import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client.js";
import { Badge, FlagBadge, SourceBadge, StatusBadge } from "../components/Badge.jsx";
import Spinner from "../components/Spinner.jsx";

const STATUS_OPTIONS = [
  { value: "", label: "any" },
  { value: "flagged", label: "flagged" },
  { value: "pending", label: "pending" },
  { value: "approved", label: "approved" },
  { value: "rejected", label: "rejected" },
];

const SOURCE_OPTIONS = [
  { value: "", label: "any" },
  { value: "sap", label: "sap" },
  { value: "utility", label: "utility" },
  { value: "travel", label: "travel" },
];

export default function ReviewPage() {
  const [params, setParams] = useSearchParams();

  const filters = useMemo(
    () => ({
      status: params.get("status") || "",
      source: params.get("source") || "",
      batch:  params.get("batch")  || "",
    }),
    [params]
  );

  const [activities, setActivities] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null); // expanded row id
  const [actioning, setActioning] = useState({}); // {id: true} while POSTing

  const fetchActivities = useCallback(() => {
    setActivities(null);
    setError(null);
    api.listActivities({ ...filters, page_size: 200 })
      .then((r) => setActivities(r.results))
      .catch((e) => setError(e.message));
  }, [filters]);

  useEffect(() => { fetchActivities(); }, [fetchActivities]);

  function updateFilter(name, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value); else next.delete(name);
    setParams(next, { replace: true });
  }

  async function decide(activityId, action) {
    const hasError = activities
      .find((a) => a.id === activityId)
      ?.flags.some((f) => f.severity === "error");
    let note = "";
    if (action === "reject" || hasError) {
      note = window.prompt(
        action === "reject"
          ? "Reason for rejection (required):"
          : "This row has an ERROR-severity flag. Provide an override note:",
        ""
      ) || "";
      if (!note.trim()) return;
    }
    setActioning((s) => ({ ...s, [activityId]: true }));
    try {
      if (action === "approve") await api.approveActivity(activityId, note);
      else await api.rejectActivity(activityId, note);
      fetchActivities();
    } catch (err) {
      alert(`Could not ${action}: ${err.message}`);
    } finally {
      setActioning((s) => {
        const copy = { ...s };
        delete copy[activityId];
        return copy;
      });
    }
  }

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Review activities</h1>
        <p className="mt-1 text-sm text-stone-600">
          Filter, inspect flags, then approve or reject. Approval is permanent - the
          row locks for audit.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-stone-200 bg-white px-4 py-3 text-sm">
        <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS}
          onChange={(v) => updateFilter("status", v)} />
        <FilterSelect label="Source" value={filters.source} options={SOURCE_OPTIONS}
          onChange={(v) => updateFilter("source", v)} />
        <FilterInput label="Batch ID" value={filters.batch}
          onChange={(v) => updateFilter("batch", v)} placeholder="e.g. 3" />
        <div className="ml-auto text-xs text-stone-500">
          {activities ? `${activities.length} rows` : ""}
        </div>
      </div>

      {error && (
        <div className="rounded border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      )}

      {activities === null && !error && <Spinner />}

      {activities && activities.length === 0 && (
        <div className="rounded-lg border border-dashed border-stone-300 bg-white p-8 text-center text-sm text-stone-500">
          No activities match these filters.
        </div>
      )}

      {activities && activities.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-stone-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-xs uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">#</th>
                <th className="px-3 py-2 text-left font-medium">source</th>
                <th className="px-3 py-2 text-left font-medium">type</th>
                <th className="px-3 py-2 text-right font-medium">qty</th>
                <th className="px-3 py-2 text-left font-medium">unit</th>
                <th className="px-3 py-2 text-left font-medium">period</th>
                <th className="px-3 py-2 text-left font-medium">location</th>
                <th className="px-3 py-2 text-left font-medium">status / flags</th>
                <th className="px-3 py-2 text-right font-medium">decide</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {activities.map((a) => (
                <Row
                  key={a.id}
                  activity={a}
                  expanded={open === a.id}
                  onToggle={() => setOpen(open === a.id ? null : a.id)}
                  onDecide={decide}
                  busy={actioning[a.id]}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Row({ activity: a, expanded, onToggle, onDecide, busy }) {
  // Both approved and rejected are terminal - buttons disable for either.
  const locked = a.status === "approved" || a.status === "rejected";
  return (
    <>
      <tr
        className={"cursor-pointer hover:bg-stone-50/60 " + (expanded ? "bg-stone-50/70" : "")}
        onClick={onToggle}
      >
        <td className="px-3 py-2 font-mono text-xs text-stone-500">{a.id}</td>
        <td className="px-3 py-2"><SourceBadge source={a.source_type} /></td>
        <td className="px-3 py-2 text-stone-800">{a.activity_type}</td>
        <td className="px-3 py-2 text-right tabular-nums font-mono">{trimDecimal(a.quantity)}</td>
        <td className="px-3 py-2 text-stone-600 font-mono text-xs">{a.unit}</td>
        <td className="px-3 py-2 font-mono text-xs text-stone-600">
          {a.period_start === a.period_end ? a.period_start : `${a.period_start} → ${a.period_end}`}
        </td>
        <td className="px-3 py-2 font-mono text-xs text-stone-600 max-w-[18ch] truncate" title={a.location_code}>
          {a.location_code || "-"}
        </td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap items-center gap-1">
            <StatusBadge status={a.status} />
            {a.flags.map((f) => <FlagBadge key={f.id} flag={f} />)}
          </div>
        </td>
        <td className="px-3 py-2 text-right">
          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
            <button
              disabled={locked || busy}
              onClick={() => onDecide(a.id, "approve")}
              className="rounded bg-emerald-700 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-800 disabled:bg-stone-300"
            >
              {busy ? "…" : "approve"}
            </button>
            <button
              disabled={locked || busy}
              onClick={() => onDecide(a.id, "reject")}
              className="rounded bg-stone-200 px-2 py-1 text-xs font-medium text-stone-800 hover:bg-stone-300 disabled:opacity-50"
            >
              reject
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="bg-stone-50/60 px-6 py-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <h3 className="text-xs uppercase tracking-wider text-stone-500 mb-2">Flags</h3>
                {a.flags.length === 0 ? (
                  <div className="text-xs text-stone-500">No flags - this row passed every rule.</div>
                ) : (
                  <ul className="space-y-1.5">
                    {a.flags.map((f) => (
                      <li key={f.id} className="flex items-start gap-2">
                        <FlagBadge flag={f} />
                        <span className="text-xs text-stone-700">{f.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <DetailField label="amount">{a.amount ? `${a.amount} ${a.currency}` : "-"}</DetailField>
                  <DetailField label="cost center">{a.cost_center || "-"}</DetailField>
                  <DetailField label="source_ref">{a.source_ref || "-"}</DetailField>
                  <DetailField label="batch"><Link to={`/review?batch=${a.batch}`} className="underline">#{a.batch}</Link></DetailField>
                </div>
              </div>
              <div>
                <h3 className="text-xs uppercase tracking-wider text-stone-500 mb-2">Raw payload</h3>
                <pre className="text-[11px] leading-snug bg-white border border-stone-200 rounded p-3 font-mono overflow-x-auto max-h-64">
                  {JSON.stringify(a.raw_payload, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-stone-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-stone-300 bg-white px-2 py-1 text-sm"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

function FilterInput({ label, value, onChange, placeholder }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-stone-500">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-28 rounded border border-stone-300 bg-white px-2 py-1 text-sm font-mono"
      />
    </label>
  );
}

function DetailField({ label, children }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className="font-mono text-stone-800">{children}</div>
    </div>
  );
}

function trimDecimal(s) {
  if (s == null) return "-";
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client.js";
import { Badge, SourceBadge } from "../components/Badge.jsx";
import Spinner from "../components/Spinner.jsx";

function fmtDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function BatchesPage() {
  const [batches, setBatches] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listBatches()
      .then((r) => setBatches(r.results))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (batches === null) return <Spinner />;
  if (batches.length === 0) return <EmptyState />;

  return (
    <div>
      <header className="mb-4 flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Ingestion batches</h1>
          <p className="mt-1 text-sm text-stone-600">
            One row per upload. Click into a batch to review its activities.
          </p>
        </div>
        <Link
          to="/upload"
          className="rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-stone-50 hover:bg-stone-700"
        >
          + new upload
        </Link>
      </header>

      <div className="overflow-hidden rounded-lg border border-stone-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-xs uppercase tracking-wider text-stone-500">
            <tr>
              <th className="px-3 py-2 text-left font-medium">#</th>
              <th className="px-3 py-2 text-left font-medium">source</th>
              <th className="px-3 py-2 text-left font-medium">filename</th>
              <th className="px-3 py-2 text-left font-medium">uploaded</th>
              <th className="px-3 py-2 text-right font-medium">rows</th>
              <th className="px-3 py-2 text-right font-medium">flagged</th>
              <th className="px-3 py-2 text-right font-medium">approved</th>
              <th className="px-3 py-2 text-right font-medium">errors</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {batches.map((b) => (
              <tr key={b.id} className="hover:bg-stone-50/60">
                <td className="px-3 py-2 font-mono text-xs text-stone-500">{b.id}</td>
                <td className="px-3 py-2"><SourceBadge source={b.source_type} /></td>
                <td className="px-3 py-2">
                  <div className="truncate max-w-[20ch]" title={b.filename}>{b.filename}</div>
                  <div className="text-[11px] text-stone-500 font-mono">{b.uploaded_by}</div>
                </td>
                <td className="px-3 py-2 text-stone-700">{fmtDate(b.uploaded_at)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{b.row_count}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {b.flagged_count > 0 ? <Badge tone="amber">{b.flagged_count}</Badge> : <span className="text-stone-400">0</span>}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {b.approved_count > 0 ? <Badge tone="green">{b.approved_count}</Badge> : <span className="text-stone-400">0</span>}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {b.error_count > 0 ? <Badge tone="red">{b.error_count}</Badge> : <span className="text-stone-400">0</span>}
                </td>
                <td className="px-3 py-2 text-right">
                  <Link
                    to={`/review?batch=${b.id}`}
                    className="text-xs underline text-stone-700 hover:text-stone-900"
                  >
                    review →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ErrorBox({ message }) {
  return (
    <div className="rounded border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
      Could not load batches: {message}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-stone-300 bg-white p-8 text-center">
      <h2 className="text-sm font-medium text-stone-700">No batches yet</h2>
      <p className="mt-1 text-xs text-stone-500">Upload a SAP, utility, or travel file to get started.</p>
      <Link
        to="/upload"
        className="mt-4 inline-block rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-stone-50 hover:bg-stone-700"
      >
        Go to upload
      </Link>
    </div>
  );
}

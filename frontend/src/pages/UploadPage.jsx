import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client.js";
import { Badge, SourceBadge } from "../components/Badge.jsx";
import Spinner from "../components/Spinner.jsx";

const SOURCES = [
  {
    key: "sap",
    title: "SAP fuel / procurement",
    hint: "Semicolon-CSV (UTF-8 or UTF-16). German or English headers.",
    accept: ".csv,.txt",
  },
  {
    key: "utility",
    title: "Utility (electricity)",
    hint: "Portal CSV export. ISO dates. kWh or MWh.",
    accept: ".csv",
  },
  {
    key: "travel",
    title: "Corporate travel (Concur-shaped)",
    hint: 'JSON with top-level "Items": [...]. Mimics Concur Expense v3.',
    accept: ".json",
  },
];

export default function UploadPage() {
  const navigate = useNavigate();
  const [results, setResults] = useState({}); // {source: {report|error}}
  const [busy, setBusy] = useState(null);

  async function handleFile(source, file) {
    setBusy(source);
    setResults((r) => ({ ...r, [source]: undefined }));
    try {
      const report = await api.uploadFile(source, file);
      setResults((r) => ({ ...r, [source]: { ok: true, report } }));
    } catch (err) {
      setResults((r) => ({ ...r, [source]: { ok: false, error: err.message } }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Upload source data</h1>
        <p className="mt-1 text-sm text-stone-600 max-w-2xl">
          Drop a file for whichever source you're onboarding. The parser
          tolerates header variations and most date / decimal formats;
          anything it cannot recover from lands in the batch error log.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {SOURCES.map((s) => (
          <div key={s.key} className="rounded-lg border border-stone-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <SourceBadge source={s.key} />
              {busy === s.key && <Spinner label="Ingesting…" />}
            </div>
            <h2 className="mt-3 text-base font-medium">{s.title}</h2>
            <p className="mt-1 text-xs text-stone-500 leading-snug">{s.hint}</p>
            <label className="mt-4 block">
              <span className="sr-only">Choose {s.title} file</span>
              <input
                type="file"
                accept={s.accept}
                disabled={busy === s.key}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (f) handleFile(s.key, f);
                }}
                className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-stone-900 file:text-stone-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:hover:bg-stone-700"
              />
            </label>

            {results[s.key] && <ResultPanel result={results[s.key]} onView={(id) => navigate(`/review?batch=${id}`)} />}
          </div>
        ))}
      </div>
    </div>
  );
}

function ResultPanel({ result, onView }) {
  if (!result.ok) {
    return (
      <div className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
        {result.error}
      </div>
    );
  }
  const { batch, rows_created, rows_failed } = result.report;
  return (
    <div className="mt-4 rounded border border-stone-200 bg-stone-50 p-3 text-xs">
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-stone-500">batch #{batch.id}</span>
        <button
          className="text-xs underline text-stone-700 hover:text-stone-900"
          onClick={() => onView(batch.id)}
        >
          review →
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge tone="green">{rows_created} rows</Badge>
        {rows_failed > 0 && <Badge tone="amber">{rows_failed} skipped</Badge>}
        {batch.flagged_count > 0 && <Badge tone="amber">{batch.flagged_count} flagged</Badge>}
      </div>
      {batch.parse_errors.length > 0 && (
        <details className="mt-2 text-stone-600">
          <summary className="cursor-pointer">Parse notes ({batch.parse_errors.length})</summary>
          <ul className="mt-1 list-disc pl-5 space-y-0.5">
            {batch.parse_errors.slice(0, 5).map((e, i) => (
              <li key={i} className="font-mono text-[11px] leading-snug">{e}</li>
            ))}
            {batch.parse_errors.length > 5 && (
              <li className="text-stone-500 italic">…and {batch.parse_errors.length - 5} more</li>
            )}
          </ul>
        </details>
      )}
    </div>
  );
}

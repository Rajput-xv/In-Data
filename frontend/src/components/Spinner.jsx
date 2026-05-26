export default function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 text-sm text-stone-500">
      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-stone-300 border-t-stone-700" />
      {label}
    </div>
  );
}

// One badge component to render every coloured pill in the app.
// Status drives colour; nothing decorative.

const TONES = {
  neutral: "bg-stone-100 text-stone-700 ring-stone-200",
  amber:   "bg-amber-50 text-amber-900 ring-amber-200",
  red:     "bg-rose-50 text-rose-900 ring-rose-200",
  green:   "bg-emerald-50 text-emerald-900 ring-emerald-200",
  blue:    "bg-sky-50 text-sky-900 ring-sky-200",
};

export function Badge({ tone = "neutral", children, mono = false, title }) {
  return (
    <span
      title={title}
      className={[
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs ring-1 ring-inset",
        TONES[tone] || TONES.neutral,
        mono ? "font-mono" : "",
      ].join(" ")}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }) {
  switch (status) {
    case "approved": return <Badge tone="green">approved</Badge>;
    case "rejected": return <Badge tone="red">rejected</Badge>;
    case "flagged":  return <Badge tone="amber">flagged</Badge>;
    case "pending":  return <Badge tone="neutral">pending</Badge>;
    default:         return <Badge>{status}</Badge>;
  }
}

export function FlagBadge({ flag }) {
  const tone = flag.severity === "error" ? "red" : "amber";
  return (
    <Badge tone={tone} mono title={flag.message}>
      {flag.rule_code}
    </Badge>
  );
}

export function SourceBadge({ source }) {
  const tone = source === "sap" ? "blue" : source === "utility" ? "neutral" : "amber";
  return <Badge tone={tone} mono>{source}</Badge>;
}

export const pct = (v, digits = 1) => (v == null ? "—" : `${(Number(v) * 100).toFixed(digits)}%`);
export const num = (v, digits = 2) => (v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(digits));
export const int = (v) => (v == null ? "—" : Number(v).toLocaleString());
export const dt = (v) => (v ? new Date(v).toLocaleString() : "—");
export const d = (v) => (v ? new Date(v).toLocaleDateString() : "—");
export const label = (s) => (s ? String(s).replace(/_/g, " ") : "—");
export const sortByDate = (rows, key) => [...rows].sort((a, b) => new Date(a[key]) - new Date(b[key]));
export const days = (v) => {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  return n < 1 ? `${(n * 24).toFixed(1)} h` : `${n.toFixed(1)} days`;
};

export const bytes = (v) => {
  const n = Number(v) || 0;
  if (n < 1024) return `${n} B`;
  return n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
};
export const signed = (v, digits = 2) => `${Number(v) >= 0 ? "+" : "−"}${Math.abs(Number(v) || 0).toFixed(digits)}`;

// <input type="datetime-local"> value <-> ISO string
export const toIso = (local) => (local ? new Date(local).toISOString() : null);
export const toLocalInput = (iso) => {
  if (!iso) return "";
  const x = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}T${p(x.getHours())}:${p(x.getMinutes())}`;
};

export const sumScores = (values) => Math.round(values.reduce((t, v) => t + (Number(v) || 0) * 100, 0)) / 100;

/** Mirrors backend apply_late_penalty(): percent of the RAW score, rounded half-up. Preview only; the API result is authoritative. */
export function previewLatePenalty(raw, percent) {
  const rawCents = Math.round((Number(raw) || 0) * 100);
  const amountCents = Math.floor((rawCents * (Number(percent) || 0)) / 100 + 0.5 + 1e-9);
  return { amount: amountCents / 100, final: Math.max(0, rawCents - amountCents) / 100 };
}

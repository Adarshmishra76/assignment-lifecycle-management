export function Spinner({ label = "Loading" }) {
  return (
    <div role="status" className="flex items-center gap-3 p-6 text-sm text-ink-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-300 border-t-brand-600" />
      {label}…
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  const forbidden = error?.status === 403;
  return (
    <div role="alert" className="rounded-md border border-mark-500/30 bg-mark-50 p-4 text-sm text-mark-700">
      <p className="font-medium">{forbidden ? "You don’t have access to this data." : "This couldn’t be loaded."}</p>
      <p className="mt-1">{error?.message || "Unknown error."}</p>
      {onRetry && !forbidden && (
        <button className="btn-quiet mt-3" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children, action }) {
  return (
    <div className="rounded-md border border-dashed border-ink-300 p-8 text-center">
      <p className="font-medium">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-md text-sm text-ink-500">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-serif text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-ink-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

const TONES = { brand: "bg-brand-500", check: "bg-check-500", mark: "bg-mark-500", flag: "bg-flag-500", muted: "bg-ink-300" };

/** A labelled proportion bar. `value` is a 0–1 fraction; `detail` states what it is a fraction of. */
export function RateBar({ label, value, display, detail, tone = "brand" }) {
  const width = Math.max(0, Math.min(1, Number(value) || 0)) * 100;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">{label}</span>
        <span className="figure text-lg">{display}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-paper-200" role="img" aria-label={`${label}: ${display}`}>
        <div className={`h-full rounded-full ${TONES[tone]}`} style={{ width: `${width}%` }} />
      </div>
      {detail && <p className="mt-1 text-xs text-ink-500">{detail}</p>}
    </div>
  );
}

/* ---------- Shared primitives used by the workflow pages ---------- */
import { useEffect } from "react";

const BADGE = {
  check: "bg-check-50 text-check-700", mark: "bg-mark-50 text-mark-700", flag: "bg-flag-50 text-flag-500",
  brand: "bg-brand-50 text-brand-700", muted: "bg-paper-100 text-ink-500",
};
export function Badge({ tone = "muted", children }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${BADGE[tone]}`}>{children}</span>;
}

const STATUS_TONE = {
  draft: "muted", published: "check", closed: "flag", archived: "muted", active: "check", enrolled: "check", dropped: "mark", completed: "brand",
  submitted: "brand", graded: "check", returned: "brand", withdrawn: "muted", requested: "flag", approved: "check", denied: "mark",
  under_review: "flag", rejected: "mark", upheld: "muted", posted: "check", revised: "brand", superseded: "muted",
  available: "check", missing: "mark", quarantined: "flag", pass: "check", fail: "mark",
};
export function StatusBadge({ status }) {
  return status ? <Badge tone={STATUS_TONE[status] || "muted"}>{String(status).replace(/_/g, " ")}</Badge> : null;
}

export function Field({ label, hint, className = "", children }) {
  return (
    <label className={`block ${className}`}>
      {label && <span className="label">{label}</span>}
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-500">{hint}</span>}
    </label>
  );
}

export function Modal({ title, onClose, children, footer, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink-900/40 sm:items-center sm:p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        className={`panel flex max-h-[92vh] w-full flex-col shadow-xl ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"}`}>
        <header className="flex items-center justify-between border-b border-paper-200 px-5 py-3">
          <h2 className="font-serif text-xl font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-xl leading-none text-ink-500 hover:text-ink-900">×</button>
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-paper-200 px-5 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

export function ConfirmModal({ title, children, confirmLabel = "Confirm", danger, busy, onConfirm, onClose }) {
  return (
    <Modal title={title} onClose={onClose} footer={<>
      <button className="btn-quiet" onClick={onClose}>Cancel</button>
      <button className={danger ? "btn-danger" : "btn-primary"} disabled={busy} onClick={onConfirm}>{busy ? "Working…" : confirmLabel}</button>
    </>}>
      <div className="space-y-2 text-sm text-ink-700">{children}</div>
    </Modal>
  );
}

/** Table with built-in loading, error and empty states. columns: [{ header, render(row), className }] */
export function DataTable({ columns, rows, loading, error, onRetry, onRowClick, emptyTitle = "Nothing here yet", emptyText, emptyAction, rowKey = "id" }) {
  if (loading && !rows?.length) return <Spinner />;
  if (error) return <div className="p-4"><ErrorState error={error} onRetry={onRetry} /></div>;
  if (!rows?.length) return <div className="p-4"><EmptyState title={emptyTitle} action={emptyAction}>{emptyText}</EmptyState></div>;
  return (
    <div className={`overflow-x-auto ${loading ? "opacity-60" : ""}`}>
      <table className="min-w-full text-sm">
        <thead className="border-b border-paper-200 bg-paper-50"><tr>{columns.map((c) => <th key={c.header} className="th">{c.header}</th>)}</tr></thead>
        <tbody className="divide-y divide-paper-200">
          {rows.map((r, i) => (
            <tr key={r[rowKey] ?? i} onClick={onRowClick && (() => onRowClick(r))} className={onRowClick ? "cursor-pointer hover:bg-paper-50" : ""}>
              {columns.map((c) => <td key={c.header} className={`td ${c.className || ""}`}>{c.render ? c.render(r) : r[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }) {
  if (!total) return null;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-paper-200 px-4 py-2.5 text-xs text-ink-500">
      <span>Showing {(page - 1) * pageSize + 1}–{Math.min(total, page * pageSize)} of {total}</span>
      <div className="flex items-center gap-2">
        <button className="btn-quiet btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span>Page {page} of {pages}</span>
        <button className="btn-quiet btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

export const FilterBar = ({ children }) => <div className="flex flex-wrap items-end gap-3 border-b border-paper-200 p-4">{children}</div>;

export function Card({ title, actions, children, padded = true, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-paper-200 px-4 py-3">
          <h2 className="font-serif text-lg font-semibold">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={padded ? "p-4" : ""}>{children}</div>
    </section>
  );
}

export const Notice = ({ tone = "mark", children }) =>
  children ? <p role="alert" className={`rounded-md p-3 text-sm ${tone === "mark" ? "bg-mark-50 text-mark-700" : "bg-flag-50 text-flag-500"}`}>{children}</p> : null;

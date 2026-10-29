import { useState } from "react";
import { datasetsApi } from "../api/endpoints";
import { Badge, Card, DataTable, EmptyState, ErrorState, Field, FilterBar, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { int, label } from "../lib/format";

const PAGE_SIZE = 15;

export default function DataQuality() {
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const run = async () => {
    setBusy(true); setError(null);
    try { setReport(await datasetsApi.validate()); setPage(1); setType(""); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const types = Object.entries(report?.by_type || {});
  const findings = (report?.findings || []).filter((f) => (!type || f.issue_type === type) && (!search || `${f.affected_entity_type} ${f.affected_entity_id} ${f.explanation}`.toLowerCase().includes(search.toLowerCase())));
  const rows = findings.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const exportCsv = () => {
    const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = ["issue_type,entity_type,entity_id,explanation", ...findings.map((f) => [f.issue_type, f.affected_entity_type, f.affected_entity_id, f.explanation].map(q).join(","))];
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    Object.assign(document.createElement("a"), { href: url, download: "data-quality-findings.csv" }).click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHeader title="Data-quality report" subtitle="Rule-based checks for integrity, grading and lifecycle anomalies." actions={<button className="btn-primary" disabled={busy} onClick={run}>{busy ? "Validating…" : report ? "Run again" : "Run validation"}</button>} />
      {error && <ErrorState error={error} onRetry={run} />}
      {!report && !busy && !error && <EmptyState title="No report yet" action={<button className="btn-primary" onClick={run}>Run validation</button>}>Run validation to check the current database. The report is also saved on the server under docs/.</EmptyState>}
      {report && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="panel p-4"><p className="text-sm text-ink-500">Overall result</p><p className="mt-1"><StatusBadge status={report.status} /></p></div>
            <div className="panel p-4"><p className="text-sm text-ink-500">Anomalies found</p><p className="figure text-3xl">{int(report.anomaly_count)}</p></div>
            <div className="panel p-4"><p className="text-sm text-ink-500">Issue types</p><p className="figure text-3xl">{types.length}</p></div>
          </div>
          {types.length > 0 && (
            <Card title="Anomalies by type"><div className="flex flex-wrap gap-2">{types.map(([t, c]) => <button key={t} onClick={() => { setType(type === t ? "" : t); setPage(1); }}><Badge tone={type === t ? "brand" : "mark"}>{label(t)} · {c}</Badge></button>)}</div></Card>
          )}
          <Card title={`Findings (${findings.length})`} padded={false} actions={findings.length > 0 && <button className="btn-quiet btn-sm" onClick={exportCsv}>Download CSV</button>}>
            <FilterBar>
              <Field label="Issue type" className="w-60"><select className="input" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}><option value="">All types</option>{types.map(([t]) => <option key={t} value={t}>{t}</option>)}</select></Field>
              <Field label="Search" className="w-64"><input className="input" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Entity or explanation" /></Field>
            </FilterBar>
            <DataTable rows={rows} rowKey="explanation" emptyTitle={report.anomaly_count ? "No findings match" : "All checks passed"} emptyText={report.anomaly_count ? "Clear the filters to see every finding." : "The detector found no anomalies in the current data."}
              columns={[{ header: "Issue", render: (f) => <Badge tone="mark">{label(f.issue_type)}</Badge> }, { header: "Entity", render: (f) => `${f.affected_entity_type} #${f.affected_entity_id}` }, { header: "Explanation", render: (f) => f.explanation }]} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={findings.length} onPage={setPage} />
          </Card>
          <p className="text-xs text-ink-500">{report.note}</p>
        </div>
      )}
    </>
  );
}

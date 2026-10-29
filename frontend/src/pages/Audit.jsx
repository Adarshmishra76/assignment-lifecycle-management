import { useState } from "react";
import { auditApi } from "../api/endpoints";
import { Badge, Card, DataTable, Field, FilterBar, PageHeader, Pagination } from "../components/ui";
import { usePaged } from "../hooks/useApi";
import { dt } from "../lib/format";

const TYPES = ["user", "course", "enrollment", "assignment", "rubric", "submission", "grade", "resubmission", "appeal"];

function Payload({ value }) {
  if (!value) return <span className="text-ink-300">—</span>;
  let pretty = value;
  try { pretty = JSON.stringify(JSON.parse(value), null, 2); } catch { /* keep raw text */ }
  return <details><summary className="cursor-pointer text-xs text-brand-600">View</summary><pre className="mt-1 max-w-xs overflow-x-auto rounded bg-paper-100 p-2 text-xs">{pretty}</pre></details>;
}

export default function Audit() {
  const list = usePaged(auditApi.list, { entity_type: "", entity_id: "" }, { pageSize: 20 });
  const [oldestFirst, setOldestFirst] = useState(false);
  const items = list.data?.items ? (oldestFirst ? [...list.data.items].reverse() : list.data.items) : [];
  const columns = [
    { header: "When", render: (e) => <span className="whitespace-nowrap">{dt(e.created_at)}</span> },
    { header: "Actor", render: (e) => (e.actor_id ? `User #${e.actor_id}` : <span className="text-ink-500">system</span>) },
    { header: "Entity", render: (e) => <span>{e.entity_type} <span className="text-ink-500">#{e.entity_id}</span></span> },
    { header: "Action", render: (e) => <Badge tone="brand">{e.action}</Badge> },
    { header: "Change", render: (e) => (e.from_state || e.to_state ? <span className="whitespace-nowrap">{e.from_state || "∅"} → <b>{e.to_state || "∅"}</b></span> : "—") },
    { header: "Details", render: (e) => <Payload value={e.payload} /> },
  ];
  return (
    <>
      <PageHeader title="Audit trail" subtitle="Every lifecycle transition and change. Newest first by default." />
      <Card padded={false}>
        <FilterBar>
          <Field label="Entity type" className="w-44"><select className="input" value={list.filters.entity_type} onChange={(e) => list.setFilters({ entity_type: e.target.value })}><option value="">All</option>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></Field>
          <Field label="Entity ID" className="w-32"><input type="number" min="1" className="input" value={list.filters.entity_id} onChange={(e) => list.setFilters({ entity_id: e.target.value })} /></Field>
          <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={oldestFirst} onChange={(e) => setOldestFirst(e.target.checked)} /> Oldest first (this page)</label>
        </FilterBar>
        <DataTable columns={columns} rows={items} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No audit events" emptyText="No events match these filters." />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
    </>
  );
}

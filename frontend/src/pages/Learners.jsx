import { useState } from "react";
import { learnersApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Card, DataTable, Field, FilterBar, Modal, Notice, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";

function CreateLearner({ onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", student_number: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    setBusy(true); setError(null);
    try { await learnersApi.create(form); toast.success("Learner created"); onSaved(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const ok = form.full_name && form.email && form.password.length >= 8 && form.student_number;
  return (
    <Modal title="New learner" onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || !ok} onClick={save}>{busy ? "Creating…" : "Create"}</button></>}>
      <div className="space-y-4">
        <Notice>{error}</Notice>
        <Field label="Full name"><input className="input" value={form.full_name} onChange={set("full_name")} /></Field>
        <Field label="Email"><input type="email" className="input" value={form.email} onChange={set("email")} /></Field>
        <Field label="Student number"><input className="input" value={form.student_number} onChange={set("student_number")} /></Field>
        <Field label="Initial password" hint="At least 8 characters"><input type="password" className="input" value={form.password} onChange={set("password")} /></Field>
      </div>
    </Modal>
  );
}

export default function Learners() {
  const { role } = useAuth();
  const lookups = useLookups();
  const list = usePaged(learnersApi.list, {}, { pageSize: 15 });
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const q = search.toLowerCase();
  const rows = (list.data?.items || []).filter((l) => !q || `${l.full_name} ${l.email} ${l.student_number}`.toLowerCase().includes(q));
  const columns = [
    { header: "Name", render: (l) => <span className="font-medium">{l.full_name || "—"}</span> },
    { header: "Email", key: "email" },
    { header: "Student no.", key: "student_number" },
    { header: "ID", key: "public_id" },
    { header: "Status", render: (l) => <StatusBadge status={l.status} /> },
  ];
  return (
    <>
      <PageHeader title="Learners" subtitle="Registered learners across all courses." />
      <Card padded={false}>
        <FilterBar>
          <Field label="Search" className="w-64"><input className="input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, email, student number" /></Field>
          <span className="pb-2 text-xs text-ink-500">Search applies to the current page.</span>
          {can.createLearner(role) && <button className="btn-primary ml-auto" onClick={() => setOpen(true)}>New learner</button>}
        </FilterBar>
        <DataTable columns={columns} rows={rows} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No learners found" emptyText="Clear the search or go to another page." />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
      {open && <CreateLearner onClose={() => setOpen(false)} onSaved={() => { setOpen(false); list.reload(); lookups.refresh(); }} />}
    </>
  );
}

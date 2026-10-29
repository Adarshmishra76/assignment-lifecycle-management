import { useState } from "react";
import { Link } from "react-router-dom";
import { assignmentsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Badge, Card, ConfirmModal, DataTable, Field, FilterBar, Modal, Notice, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi, usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { dt, toIso, toLocalInput } from "../lib/format";

const BLANK = { course_id: "", title: "", description: "", due_at: "", allow_late: true, late_penalty_percent: "10", max_resubmissions: "1", resubmission_policy: "instructor_approval" };
const POLICY = { none: "No resubmissions", instructor_approval: "An instructor approves each request", automatic: "Requests are approved automatically" };

function AssignmentForm({ assignment, onClose, onSaved }) {
  const { courses } = useLookups();
  const toast = useToast();
  const editing = Boolean(assignment);
  const [form, setForm] = useState(editing ? { course_id: assignment.course_id, title: assignment.title, description: assignment.description || "", due_at: toLocalInput(assignment.due_at), allow_late: assignment.allow_late, late_penalty_percent: String(Number(assignment.late_penalty_percent)), max_resubmissions: String(assignment.max_resubmissions), resubmission_policy: assignment.resubmission_policy } : BLANK);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const save = async () => {
    setBusy(true); setError(null);
    const body = { title: form.title, description: form.description || null, due_at: toIso(form.due_at), allow_late: form.allow_late, late_penalty_percent: Number(form.late_penalty_percent), max_resubmissions: Number(form.max_resubmissions), resubmission_policy: form.resubmission_policy };
    try {
      if (editing) await assignmentsApi.update(assignment.id, body);
      else await assignmentsApi.create({ ...body, course_id: Number(form.course_id) });
      toast.success(editing ? "Assignment updated" : "Draft assignment created");
      onSaved();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal wide title={editing ? "Edit assignment" : "New assignment"} onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || !form.title || (!editing && !form.course_id)} onClick={save}>{busy ? "Saving…" : editing ? "Save changes" : "Create draft"}</button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><Notice>{error}</Notice></div>
        {!editing && <Field label="Course" className="sm:col-span-2"><select className="input" value={form.course_id} onChange={set("course_id")}><option value="">Select a course…</option>{courses.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}</select></Field>}
        <Field label="Title" className="sm:col-span-2"><input className="input" value={form.title} onChange={set("title")} /></Field>
        <Field label="Description" className="sm:col-span-2"><textarea rows={3} className="input" value={form.description} onChange={set("description")} /></Field>
        <Field label="Due date" hint="Required before publishing"><input type="datetime-local" className="input" value={form.due_at} onChange={set("due_at")} /></Field>
        <Field label="Late submissions"><span className="flex h-[38px] items-center gap-2 text-sm"><input type="checkbox" checked={form.allow_late} onChange={set("allow_late")} /> Allow late work</span></Field>
        <Field label="Late penalty (%)" hint="Percent of the raw score deducted"><input type="number" min="0" max="100" step="0.01" className="input" disabled={!form.allow_late} value={form.late_penalty_percent} onChange={set("late_penalty_percent")} /></Field>
        <Field label="Max resubmissions"><input type="number" min="0" className="input" value={form.max_resubmissions} onChange={set("max_resubmissions")} /></Field>
        <Field label="Resubmission policy" hint={POLICY[form.resubmission_policy]} className="sm:col-span-2"><select className="input" value={form.resubmission_policy} onChange={set("resubmission_policy")}><option>none</option><option>instructor_approval</option><option>automatic</option></select></Field>
      </div>
    </Modal>
  );
}

function Versions({ assignment, onClose }) {
  const { data, loading, error, reload } = useApi(() => assignmentsApi.versions(assignment.id), [assignment.id]);
  const rows = [...(data || [])].sort((a, b) => a.version_number - b.version_number);
  return (
    <Modal title={`Versions · ${assignment.title}`} onClose={onClose}>
      <DataTable rows={rows} loading={loading} error={error} onRetry={reload} emptyTitle="No published versions" emptyText="A version is created each time the assignment is published."
        columns={[{ header: "Version", render: (v) => `v${v.version_number}` }, { header: "Published", render: (v) => dt(v.published_at) }, { header: "Due", render: (v) => dt(v.due_at) }, { header: "Rubric", render: (v) => (v.rubric_id ? `#${v.rubric_id}` : "—") }]} />
    </Modal>
  );
}

export default function Assignments() {
  const { role } = useAuth();
  const toast = useToast();
  const lookups = useLookups();
  const manage = can.manageAssignments(role);
  const list = usePaged(assignmentsApi.list, { course_id: "" }, { pageSize: 10 });
  const [status, setStatus] = useState("");
  const [form, setForm] = useState(null);
  const [versions, setVersions] = useState(null);
  const [toPublish, setToPublish] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState(null);
  const rows = (list.data?.items || []).filter((a) => !status || a.status === status);

  const publish = async () => {
    setPublishing(true); setPublishError(null);
    try { await assignmentsApi.publish(toPublish.id); toast.success(`“${toPublish.title}” published`); setToPublish(null); list.reload(); lookups.refresh(); }
    catch (e) { setPublishError(e.message); } finally { setPublishing(false); }
  };
  const columns = [
    { header: "Title", render: (a) => <div><p className="font-medium">{a.title}</p><p className="text-xs text-ink-500">{a.public_id}</p></div> },
    { header: "Course", render: (a) => lookups.courseCode(a.course_id) },
    { header: "Status", render: (a) => <StatusBadge status={a.status} /> },
    { header: "Due", render: (a) => dt(a.due_at) },
    { header: "Late policy", render: (a) => (a.allow_late ? <Badge tone="flag">{Number(a.late_penalty_percent)}% penalty</Badge> : <Badge>No late work</Badge>) },
    { header: "Resubmit", render: (a) => (a.resubmission_policy === "none" ? "—" : `${a.max_resubmissions} · ${a.resubmission_policy.replace("_", " ")}`) },
    { header: "Actions", render: (a) => (
      <div className="flex flex-wrap gap-1.5">
        {manage && a.status !== "archived" && <button className="btn-quiet btn-sm" onClick={() => setForm({ assignment: a })}>Edit</button>}
        {manage && <Link className="btn-quiet btn-sm" to={`/assignments/${a.id}/rubric`}>Rubric</Link>}
        {manage && a.status === "draft" && <button className="btn-primary btn-sm" onClick={() => { setPublishError(null); setToPublish(a); }}>Publish</button>}
        <button className="btn-quiet btn-sm" onClick={() => setVersions(a)}>Versions</button>
      </div>) },
  ];
  return (
    <>
      <PageHeader title="Assignments" subtitle="Create a draft, attach a rubric, then publish." actions={manage && <button className="btn-primary" onClick={() => setForm({})}>New assignment</button>} />
      <Card padded={false}>
        <FilterBar>
          <Field label="Course" className="w-64"><select className="input" value={list.filters.course_id} onChange={(e) => list.setFilters({ course_id: e.target.value })}><option value="">All courses</option>{lookups.courses.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}</select></Field>
          <Field label="Status" className="w-40"><select className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{["draft", "published", "closed", "archived"].map((s) => <option key={s}>{s}</option>)}</select></Field>
          <span className="pb-2 text-xs text-ink-500">Status filter applies to the current page.</span>
        </FilterBar>
        <DataTable columns={columns} rows={rows} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No assignments" emptyText={manage ? "Create a draft, add a rubric, and publish it." : "No assignments match your filters."} />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
      {form && <AssignmentForm assignment={form.assignment} onClose={() => setForm(null)} onSaved={() => { setForm(null); list.reload(); lookups.refresh(); }} />}
      {versions && <Versions assignment={versions} onClose={() => setVersions(null)} />}
      {toPublish && (
        <ConfirmModal title="Publish assignment?" confirmLabel="Publish" busy={publishing} onClose={() => setToPublish(null)} onConfirm={publish}>
          <p>Publishing creates a new version of <b>{toPublish.title}</b> and opens it for submissions.</p>
          <ul className="list-disc pl-5 text-xs text-ink-500"><li>A rubric with at least one criterion is required.</li><li>A due date in the future is required.</li></ul>
          <Notice>{publishError}</Notice>
        </ConfirmModal>
      )}
    </>
  );
}

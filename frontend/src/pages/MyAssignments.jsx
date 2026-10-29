import { useState } from "react";
import { Link } from "react-router-dom";
import { submissionsApi } from "../api/endpoints";
import { assignmentsApi } from "../api/endpoints";
import ArtifactPicker from "../components/ArtifactPicker";
import { Badge, Card, DataTable, ErrorState, Modal, Notice, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi, usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { dt } from "../lib/format";

function SubmitModal({ assignment, onClose, onSaved }) {
  const toast = useToast();
  const [artifacts, setArtifacts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const overdue = assignment.due_at && new Date() > new Date(assignment.due_at);
  const submit = async () => {
    setBusy(true); setError(null);
    try { await submissionsApi.create({ assignment_id: assignment.id, artifacts }); toast.success("Submission received"); onSaved(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal title={`Submit · ${assignment.title}`} onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy} onClick={submit}>{busy ? "Submitting…" : "Submit work"}</button></>}>
      <div className="space-y-4">
        <Notice>{error}</Notice>
        {overdue && <Notice tone="flag">{assignment.allow_late ? `The due date has passed. This will be marked late and a ${Number(assignment.late_penalty_percent)}% penalty may apply.` : "The due date has passed and late work is not accepted for this assignment."}</Notice>}
        <ArtifactPicker value={artifacts} onChange={setArtifacts} />
        {artifacts.length === 0 && <p className="text-xs text-flag-500">No files attached. You can still submit, but the work will have no artifacts.</p>}
        <p className="text-xs text-ink-500">You can submit once. Further attempts go through a resubmission request.</p>
      </div>
    </Modal>
  );
}

export default function MyAssignments() {
  const { courseName } = useLookups();
  const list = usePaged(assignmentsApi.list, {}, { pageSize: 10 });
  const subs = useApi(() => submissionsApi.list({ page_size: 100 }), []);
  const [target, setTarget] = useState(null);
  const latest = {};
  (subs.data?.items || []).forEach((s) => { if (!latest[s.assignment_id] || s.version_number > latest[s.assignment_id].version_number) latest[s.assignment_id] = s; });
  const columns = [
    { header: "Assignment", render: (a) => <div><p className="font-medium">{a.title}</p><p className="text-xs text-ink-500">{courseName(a.course_id)}</p></div> },
    { header: "Due", render: (a) => <div>{dt(a.due_at)}{a.due_at && new Date() > new Date(a.due_at) && !latest[a.id] && a.status === "published" && <div><Badge tone="mark">Overdue</Badge></div>}</div> },
    { header: "Status", render: (a) => <StatusBadge status={a.status} /> },
    { header: "Late policy", render: (a) => (a.allow_late ? `${Number(a.late_penalty_percent)}% penalty` : "Not accepted") },
    { header: "My submission", render: (a) => latest[a.id] ? <span className="flex items-center gap-2"><StatusBadge status={latest[a.id].status} /><span className="text-xs text-ink-500">v{latest[a.id].version_number}</span>{latest[a.id].is_late && <Badge tone="flag">late</Badge>}</span> : <span className="text-ink-500">Not submitted</span> },
    { header: "", render: (a) => latest[a.id]
      ? <Link className="text-brand-600 hover:underline" to={`/submissions/${latest[a.id].id}`}>View</Link>
      : a.status === "published" ? <button className="btn-primary btn-sm" onClick={() => setTarget(a)}>Submit</button> : <span className="text-xs text-ink-500">Closed</span> },
  ];
  return (
    <>
      <PageHeader title="My assignments" subtitle="Published work for the courses you are enrolled in." />
      {subs.error && <div className="mb-3"><ErrorState error={subs.error} onRetry={subs.reload} /></div>}
      <Card padded={false}>
        <DataTable columns={columns} rows={list.data?.items} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No assignments yet" emptyText="Assignments appear once an instructor publishes them for a course you are enrolled in." />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
      {target && <SubmitModal assignment={target} onClose={() => setTarget(null)} onSaved={() => { setTarget(null); subs.reload(); list.reload(); }} />}
    </>
  );
}

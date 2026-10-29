import { useState } from "react";
import { Link } from "react-router-dom";
import { resubmissionsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import ArtifactPicker from "../components/ArtifactPicker";
import { Card, DataTable, Field, FilterBar, Modal, Notice, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { dt } from "../lib/format";

function DecisionModal({ item, approve, onClose, onSaved }) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const save = async () => {
    setBusy(true); setError(null);
    try { await resubmissionsApi.decide(item.id, { approved: approve, reason: reason.trim() }); toast.success(approve ? "Resubmission approved" : "Resubmission denied"); onSaved(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal title={`${approve ? "Approve" : "Deny"} ${item.public_id}`} onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className={approve ? "btn-primary" : "btn-danger"} disabled={busy || !reason.trim()} onClick={save}>{busy ? "Saving…" : approve ? "Approve" : "Deny"}</button></>}>
      <div className="space-y-3"><Notice>{error}</Notice><Field label="Reason (required)"><textarea rows={3} className="input" value={reason} onChange={(e) => setReason(e.target.value)} /></Field></div>
    </Modal>
  );
}

function AttemptModal({ item, onClose, onSaved }) {
  const toast = useToast();
  const [artifacts, setArtifacts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const save = async () => {
    setBusy(true); setError(null);
    try { await resubmissionsApi.submit(item.id, { assignment_id: item.assignment_id, artifacts }); toast.success("New attempt submitted"); onSaved(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal title="Submit new attempt" onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy} onClick={save}>{busy ? "Submitting…" : "Submit attempt"}</button></>}>
      <div className="space-y-3"><Notice>{error}</Notice><ArtifactPicker value={artifacts} onChange={setArtifacts} /></div>
    </Modal>
  );
}

export default function Resubmissions() {
  const { role } = useAuth();
  const { assignmentTitle, learnerName } = useLookups();
  const list = usePaged(resubmissionsApi.list, {}, { pageSize: 10 });
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
  const staff = can.viewLearners(role);
  const rows = (list.data?.items || []).filter((r) => !status || r.status === status);
  const columns = [
    { header: "Request", render: (r) => <span className="font-medium">{r.public_id}</span> },
    { header: "Assignment", render: (r) => assignmentTitle(r.assignment_id) },
    ...(staff ? [{ header: "Learner", render: (r) => learnerName(r.learner_id) }] : []),
    { header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { header: "Requested", render: (r) => dt(r.requested_at) },
    { header: "Decision", render: (r) => <div><p className="text-xs text-ink-500">{dt(r.decided_at)}</p><p className="max-w-xs truncate" title={r.decision_reason || ""}>{r.decision_reason || "—"}</p></div> },
    { header: "Attempts", render: (r) => <div className="flex flex-col text-xs"><Link className="text-brand-600 hover:underline" to={`/submissions/${r.previous_submission_id}`}>Previous attempt</Link>{r.resulting_submission_id && <Link className="text-brand-600 hover:underline" to={`/submissions/${r.resulting_submission_id}`}>New attempt</Link>}</div> },
    { header: "Actions", render: (r) => (
      <div className="flex gap-1.5">
        {can.decideResubmission(role) && r.status === "requested" && <><button className="btn-primary btn-sm" onClick={() => setModal({ item: r, approve: true })}>Approve</button><button className="btn-quiet btn-sm" onClick={() => setModal({ item: r, approve: false })}>Deny</button></>}
        {can.requestResubmission(role) && r.status === "approved" && <button className="btn-primary btn-sm" onClick={() => setModal({ item: r, attempt: true })}>Submit attempt</button>}
      </div>) },
  ];
  const close = () => setModal(null);
  const saved = () => { close(); list.reload(); };
  return (
    <>
      <PageHeader title="Resubmissions" subtitle={staff ? "Review and decide requests for another attempt." : "Request another attempt from a graded submission, then submit it once approved."} />
      <Card padded={false}>
        <FilterBar><Field label="Status" className="w-44"><select className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{["requested", "approved", "denied", "completed"].map((s) => <option key={s}>{s}</option>)}</select></Field><span className="pb-2 text-xs text-ink-500">Filter applies to the current page.</span></FilterBar>
        <DataTable columns={columns} rows={rows} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No resubmissions" emptyText={can.requestResubmission(role) ? "Open a graded submission under Grades & feedback to request one." : "No requests match your filters."} />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
      {modal && !modal.attempt && <DecisionModal item={modal.item} approve={modal.approve} onClose={close} onSaved={saved} />}
      {modal?.attempt && <AttemptModal item={modal.item} onClose={close} onSaved={saved} />}
    </>
  );
}

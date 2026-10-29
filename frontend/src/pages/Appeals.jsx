import { useState } from "react";
import { Link } from "react-router-dom";
import { appealsApi, assignmentsApi, gradesApi, submissionsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import ScoreBreakdown from "../components/ScoreBreakdown";
import { Badge, Card, DataTable, ErrorState, Field, FilterBar, Modal, Notice, PageHeader, Pagination, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi, usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { dt, num } from "../lib/format";

function DetailModal({ appeal, onClose }) {
  return (
    <Modal title={`Appeal ${appeal.public_id}`} onClose={onClose}>
      <dl className="space-y-3 text-sm">
        <div><dt className="label">Status</dt><dd><StatusBadge status={appeal.status} /></dd></div>
        <div><dt className="label">Learner’s reason</dt><dd className="whitespace-pre-wrap">{appeal.reason}</dd></div>
        {appeal.evidence_refs && <div><dt className="label">Evidence</dt><dd className="whitespace-pre-wrap">{appeal.evidence_refs}</dd></div>}
        <div><dt className="label">Filed</dt><dd>{dt(appeal.created_at)}</dd></div>
        {appeal.decision && <><div><dt className="label">Decision</dt><dd><StatusBadge status={appeal.decision} /> · {dt(appeal.decided_at)}</dd></div><div><dt className="label">Decision reason</dt><dd className="whitespace-pre-wrap">{appeal.decision_reason}</dd></div></>}
        {appeal.resulting_grade_id && <div><dt className="label">Resulting grade</dt><dd><Link className="text-brand-600 hover:underline" to={`/grades/${appeal.submission_id}`}>View revised grade</Link></dd></div>}
      </dl>
    </Modal>
  );
}

function DecideModal({ appeal, onClose, onSaved }) {
  const toast = useToast();
  const [decision, setDecision] = useState("rejected");
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState("");
  const [edited, setEdited] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const ctx = useApi(async () => {
    const [submission, grade] = await Promise.all([submissionsApi.get(appeal.submission_id), gradesApi.get(appeal.grade_id)]);
    const [assignment, rubric] = await Promise.all([assignmentsApi.get(submission.assignment_id), assignmentsApi.rubric(submission.assignment_id)]);
    return { submission, grade, assignment, rubric };
  }, [appeal.id]);
  const criteria = ctx.data ? [...ctx.data.rubric.criteria].sort((a, b) => a.sort_order - b.sort_order) : [];
  const scores = edited || (ctx.data ? Object.fromEntries(ctx.data.grade.scores.map((s) => [s.criterion_id, String(Number(s.score))])) : {});
  const bad = criteria.some((c) => scores[c.id] === "" || scores[c.id] === undefined || Number(scores[c.id]) < 0 || Number(scores[c.id]) > Number(c.max_score));
  const save = async () => {
    setBusy(true); setError(null);
    try {
      await appealsApi.decide(appeal.id, { decision, decision_reason: reason.trim(), scores: decision === "approved" ? criteria.map((c) => ({ criterion_id: c.id, score: Number(scores[c.id]) })) : null, feedback: feedback.trim() || null });
      toast.success(`Appeal ${decision}`); onSaved();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal wide title={`Decide ${appeal.public_id}`} onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || !ctx.data || !reason.trim() || (decision === "approved" && bad)} onClick={save}>{busy ? "Saving…" : "Record decision"}</button></>}>
      {ctx.loading ? <Spinner /> : ctx.error ? <ErrorState error={ctx.error} onRetry={ctx.reload} /> : (
        <div className="space-y-4">
          <Notice>{error}</Notice>
          <div className="rounded-md bg-paper-100 p-3 text-sm"><p className="label">Learner’s reason</p><p className="whitespace-pre-wrap">{appeal.reason}</p>{appeal.evidence_refs && <p className="mt-2 text-xs text-ink-500">Evidence: {appeal.evidence_refs}</p>}</div>
          <Field label="Decision"><select className="input" value={decision} onChange={(e) => setDecision(e.target.value)}><option value="rejected">Rejected: grade unchanged</option><option value="upheld">Upheld: original grade stands</option><option value="approved">Approved: revise the grade</option></select></Field>
          {decision === "approved" ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">Revised criterion scores <span className="font-normal text-ink-500">(current grade pre-filled)</span></p>
              {criteria.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-3 text-sm"><span>{c.name}</span>
                  <span className="flex items-center gap-2"><input type="number" min="0" max={c.max_score} step="0.01" aria-label={`Score for ${c.name}`} className="input w-28" value={scores[c.id] ?? ""} onChange={(e) => setEdited({ ...scores, [c.id]: e.target.value })} /><span className="text-xs text-ink-500">/ {num(c.max_score)}</span></span></div>
              ))}
              <ScoreBreakdown criteria={criteria} scores={scores} latePercent={ctx.data.assignment.late_penalty_percent} applyPenalty={ctx.data.grade.late_penalty_applied || (ctx.data.submission.is_late && ctx.data.assignment.allow_late)} isLate={ctx.data.submission.is_late} />
            </div>
          ) : <p className="text-xs text-ink-500">The current grade ({num(ctx.data.grade.final_score)}) will not change.</p>}
          <Field label="Decision reason (required)"><textarea rows={3} className="input" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <Field label="Feedback to learner (optional)"><textarea rows={2} className="input" value={feedback} onChange={(e) => setFeedback(e.target.value)} /></Field>
        </div>
      )}
    </Modal>
  );
}

export default function Appeals() {
  const { role } = useAuth();
  const toast = useToast();
  const { learnerName } = useLookups();
  const list = usePaged(appealsApi.list, {}, { pageSize: 10 });
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const staff = can.viewLearners(role);
  const rows = (list.data?.items || []).filter((a) => !status || a.status === status);
  const startReview = async (a) => {
    setBusyId(a.id);
    try { await appealsApi.review(a.id); toast.success("Review started"); list.reload(); } catch (e) { toast.error(e.message); } finally { setBusyId(null); }
  };
  const columns = [
    { header: "Appeal", render: (a) => <span className="font-medium">{a.public_id}</span> },
    ...(staff ? [{ header: "Learner", render: (a) => learnerName(a.learner_id) }] : []),
    { header: "Reason", render: (a) => <span className="line-clamp-2 max-w-xs" title={a.reason}>{a.reason}</span> },
    { header: "Status", render: (a) => <StatusBadge status={a.status} /> },
    { header: "Outcome", render: (a) => (a.decision ? <Badge tone={a.decision === "approved" ? "check" : a.decision === "rejected" ? "mark" : "muted"}>{a.decision}</Badge> : "—") },
    { header: "Filed", render: (a) => dt(a.created_at) },
    { header: "Actions", render: (a) => (
      <div className="flex flex-wrap gap-1.5">
        <button className="btn-quiet btn-sm" onClick={() => setModal({ view: a })}>Details</button>
        {can.reviewAppeal(role) && a.status === "submitted" && <button className="btn-primary btn-sm" disabled={busyId === a.id} onClick={() => startReview(a)}>{busyId === a.id ? "Starting…" : "Start review"}</button>}
        {can.reviewAppeal(role) && a.status === "under_review" && <button className="btn-primary btn-sm" onClick={() => setModal({ decide: a })}>Decide</button>}
        <Link className="btn-quiet btn-sm" to={`/grades/${a.submission_id}`}>Grade</Link>
      </div>) },
  ];
  return (
    <>
      <PageHeader title="Appeals" subtitle={can.fileAppeal(role) ? "Track your grade appeals. File one from Grades & feedback." : "Review learner appeals and record decisions."} />
      <Card padded={false}>
        <FilterBar><Field label="Status" className="w-44"><select className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{["submitted", "under_review", "approved", "rejected", "upheld"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></Field><span className="pb-2 text-xs text-ink-500">Filter applies to the current page.</span></FilterBar>
        <DataTable columns={columns} rows={rows} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No appeals" emptyText="Appeals appear here once a learner contests a grade." />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
      {modal?.view && <DetailModal appeal={modal.view} onClose={() => setModal(null)} />}
      {modal?.decide && <DecideModal appeal={modal.decide} onClose={() => setModal(null)} onSaved={() => { setModal(null); list.reload(); }} />}
    </>
  );
}

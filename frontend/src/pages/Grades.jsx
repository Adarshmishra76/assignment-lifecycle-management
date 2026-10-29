import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { appealsApi, assignmentsApi, gradesApi, resubmissionsApi, submissionsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import ScoreBreakdown from "../components/ScoreBreakdown";
import { Badge, Card, ErrorState, Field, Modal, Notice, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { dt, num, signed, sumScores } from "../lib/format";
import { SubmissionList } from "./Submissions";

export function GradesList() {
  return <SubmissionList title="Grades & feedback" subtitle="Graded work. Open one to see scoring, feedback and every grade revision." defaultStatus="graded" statusOptions={["graded", "returned"]} linkTo={(s) => `/grades/${s.id}`} emptyTitle="No graded work yet" emptyText="Grades appear here once instructors have scored submissions." />;
}

function ReviseModal({ grade, criteria, submission, assignment, onClose, onSaved }) {
  const toast = useToast();
  const [scores, setScores] = useState(Object.fromEntries(grade.scores.map((s) => [s.criterion_id, String(Number(s.score))])));
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const bad = criteria.some((c) => scores[c.id] === "" || scores[c.id] === undefined || Number(scores[c.id]) < 0 || Number(scores[c.id]) > Number(c.max_score));
  // Server rule: the penalty stays if it was applied, or if the work is late and late work is allowed.
  const penalty = grade.late_penalty_applied || (submission.is_late && assignment.allow_late);
  const save = async () => {
    setBusy(true); setError(null);
    try { await gradesApi.revise(grade.id, { scores: criteria.map((c) => ({ criterion_id: c.id, score: Number(scores[c.id]) })), reason: reason.trim(), feedback: feedback.trim() || null }); toast.success("Grade revised"); onSaved(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal wide title="Revise grade" onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || bad || !reason.trim()} onClick={save}>{busy ? "Saving…" : "Save revision"}</button></>}>
      <div className="space-y-4">
        <Notice>{error}</Notice>
        {criteria.map((c) => (
          <div key={c.id} className="flex items-center justify-between gap-3 text-sm"><span>{c.name}</span>
            <span className="flex items-center gap-2"><input type="number" min="0" max={c.max_score} step="0.01" aria-label={`Score for ${c.name}`} className="input w-28" value={scores[c.id] ?? ""} onChange={(e) => setScores({ ...scores, [c.id]: e.target.value })} /><span className="text-xs text-ink-500">/ {num(c.max_score)}</span></span></div>
        ))}
        <ScoreBreakdown criteria={criteria} scores={scores} latePercent={assignment.late_penalty_percent} applyPenalty={penalty} isLate={submission.is_late} />
        <Field label="Reason for change (required)" hint="Recorded in the grade history and audit trail"><textarea rows={3} className="input" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <Field label="Feedback (optional)"><textarea rows={2} className="input" value={feedback} onChange={(e) => setFeedback(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

function AppealModal({ grade, onClose, onSaved }) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const save = async () => {
    setBusy(true); setError(null);
    try { await appealsApi.create({ grade_id: grade.id, reason: reason.trim(), evidence_refs: evidence.trim() || null }); toast.success("Appeal filed"); onSaved(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal title="Appeal this grade" onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || !reason.trim()} onClick={save}>{busy ? "Filing…" : "File appeal"}</button></>}>
      <div className="space-y-4">
        <Notice>{error}</Notice>
        <p className="text-sm text-ink-500">Appealing revision {grade.revision_number} (final score {num(grade.final_score)}). One appeal is allowed per grade.</p>
        <Field label="Reason"><textarea rows={4} className="input" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <Field label="Evidence references (optional)"><input className="input" value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="Links, file names, page numbers" /></Field>
      </div>
    </Modal>
  );
}

export default function GradeDetail() {
  const { submissionId } = useParams();
  const { role } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { assignmentTitle, learnerName } = useLookups();
  const [picked, setPicked] = useState(null);
  const [modal, setModal] = useState(null);
  const [busy, setBusy] = useState(false);
  const { data, loading, error, reload } = useApi(async () => {
    const submission = await submissionsApi.get(submissionId);
    const [assignment, grades, feedback, revisions, rubric] = await Promise.all([
      assignmentsApi.get(submission.assignment_id), submissionsApi.grades(submissionId), submissionsApi.feedback(submissionId), submissionsApi.revisions(submissionId),
      assignmentsApi.rubric(submission.assignment_id).catch((e) => (e.status === 404 ? null : Promise.reject(e))),
    ]);
    return { submission, assignment, grades, feedback, revisions, rubric };
  }, [submissionId]);

  if (loading) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const { submission, assignment, grades, feedback, revisions, rubric } = data;
  const criteria = rubric ? [...rubric.criteria].sort((a, b) => a.sort_order - b.sort_order) : [];
  const current = grades.find((g) => g.is_current) || grades[grades.length - 1];
  const shown = grades.find((g) => g.id === picked) || current;
  const byGrade = Object.fromEntries(grades.map((g) => [g.id, g]));
  // One chronological timeline: grade revisions and feedback, oldest first.
  const events = [
    ...revisions.map((r) => ({ kind: "revision", at: r.created_at, id: `r${r.id}`, r })),
    ...feedback.map((f) => ({ kind: "feedback", at: f.created_at, id: `f${f.id}`, f })),
  ].sort((a, b) => new Date(a.at) - new Date(b.at));
  const matched = shown ? sumScores(criteria.map((c) => shown.scores.find((s) => s.criterion_id === c.id)?.score)) : 0;
  const mismatch = shown && criteria.length > 0 && Math.abs(matched - Number(shown.raw_score)) > 0.005;

  const requestResubmission = async () => {
    setBusy(true);
    try { await resubmissionsApi.request({ assignment_id: submission.assignment_id, previous_submission_id: submission.id }); toast.success("Resubmission requested"); navigate("/resubmissions"); }
    catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };

  return (
    <>
      <Link to="/grades" className="mb-3 inline-block text-sm text-ink-500 hover:text-ink-900">← Grades & feedback</Link>
      <PageHeader title={assignmentTitle(submission.assignment_id)} subtitle={`${can.viewLearners(role) ? `${learnerName(submission.learner_id)} · ` : ""}${submission.public_id} · v${submission.version_number} · submitted ${dt(submission.submitted_at)}`}
        actions={<div className="flex flex-wrap gap-2">
          <Link className="btn-quiet" to={`/submissions/${submission.id}`}>Submission & artifacts</Link>
          {current && can.grade(role) && rubric && <button className="btn-primary" onClick={() => setModal("revise")}>Revise grade</button>}
          {current && can.fileAppeal(role) && <button className="btn-quiet" onClick={() => setModal("appeal")}>Appeal</button>}
          {can.requestResubmission(role) && assignment.resubmission_policy !== "none" && <button className="btn-quiet" disabled={busy} onClick={requestResubmission}>{busy ? "Requesting…" : "Request resubmission"}</button>}
        </div>} />

      {!current ? <Card><p className="py-8 text-center text-sm text-ink-500">Not graded yet (status: <StatusBadge status={submission.status} />).</p></Card> : (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
          <div className="space-y-4">
            <Card title={<span className="flex items-center gap-2">Revision {shown.revision_number} <StatusBadge status={shown.status} />{shown.is_current && <Badge tone="brand">current</Badge>}</span>} actions={<span className="text-xs text-ink-500">{dt(shown.created_at)}</span>}>
              {rubric ? <ScoreBreakdown criteria={criteria} grade={shown} latePercent={assignment.late_penalty_percent} isLate={submission.is_late} />
                : <p className="text-sm text-ink-500">Rubric unavailable. Raw {num(shown.raw_score)}, penalty −{num(shown.late_penalty_amount)}, final {num(shown.final_score)}.</p>}
              {mismatch && <p className="mt-2 text-xs text-flag-500">The rubric was edited after this grade was posted, so the rows may not add up to the stored raw score ({num(shown.raw_score)}).</p>}
            </Card>
            {grades.length > 1 && (
              <Card title="Grade versions, oldest first" padded={false}>
                <ul className="divide-y divide-paper-200 text-sm">
                  {grades.map((g) => (
                    <li key={g.id}><button onClick={() => setPicked(g.id)} className={`flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-paper-50 ${g.id === shown.id ? "bg-brand-50" : ""}`}>
                      <span>Revision {g.revision_number} · {dt(g.created_at)}</span><span className="flex items-center gap-2"><StatusBadge status={g.status} /><b>{num(g.final_score)}</b></span></button></li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
          <Card title="History, oldest first">
            {events.length === 0 ? <p className="text-sm text-ink-500">No history recorded.</p> : (
              <ol className="relative ml-2 space-y-4 border-l-2 border-paper-200 pl-5">
                {events.map((e) => (
                  <li key={e.id} className="relative text-sm">
                    <span className={`absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-white ${e.kind === "revision" ? "bg-brand-600" : "bg-check-500"}`} />
                    <p className="text-xs text-ink-500">{dt(e.at)}</p>
                    {e.kind === "revision" ? (
                      <div>
                        <p className="font-medium">Revision {byGrade[e.r.grade_id]?.revision_number ?? "?"}: {e.r.previous_final_score === null ? <>initial grade <b>{num(e.r.new_final_score)}</b></> : <>{num(e.r.previous_final_score)} → <b>{num(e.r.new_final_score)}</b> <span className={Number(e.r.new_final_score) >= Number(e.r.previous_final_score) ? "text-check-700" : "text-mark-700"}>({signed(Number(e.r.new_final_score) - Number(e.r.previous_final_score))})</span></>}</p>
                        <p className="text-ink-700">Reason: {e.r.reason}</p><p className="text-xs text-ink-500">by user #{e.r.changed_by_id}</p>
                      </div>
                    ) : (
                      <div><p className="font-medium">Feedback</p><p className="whitespace-pre-wrap text-ink-700">{e.f.body}</p><p className="text-xs text-ink-500">by user #{e.f.author_id}</p></div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      )}
      {modal === "revise" && <ReviseModal grade={current} criteria={criteria} submission={submission} assignment={assignment} onClose={() => setModal(null)} onSaved={() => { setModal(null); setPicked(null); reload(); }} />}
      {modal === "appeal" && <AppealModal grade={current} onClose={() => setModal(null)} onSaved={() => { setModal(null); navigate("/appeals"); }} />}
    </>
  );
}

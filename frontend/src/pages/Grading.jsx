import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { assignmentsApi, gradesApi, submissionsApi } from "../api/endpoints";
import ScoreBreakdown from "../components/ScoreBreakdown";
import { Badge, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Pagination, Spinner } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi, usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { dt, num } from "../lib/format";
import { ArtifactTable } from "./Submissions";

function GradeForm({ submission, onGraded }) {
  const toast = useToast();
  const { learnerName, assignmentTitle } = useLookups();
  const ctx = useApi(async () => {
    const [assignment, rubric] = await Promise.all([assignmentsApi.get(submission.assignment_id), assignmentsApi.rubric(submission.assignment_id)]);
    return { assignment, rubric };
  }, [submission.id]);
  const [scores, setScores] = useState({});
  const [feedback, setFeedback] = useState("");
  const [penalty, setPenalty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setScores({}); setFeedback(""); setError(null);
    if (ctx.data) setPenalty(Boolean(submission.is_late && ctx.data.assignment.allow_late && Number(ctx.data.assignment.late_penalty_percent) > 0));
  }, [submission.id, ctx.data]);

  if (ctx.loading) return <Spinner />;
  if (ctx.error) return ctx.error.status === 404
    ? <EmptyState title="No rubric yet">This assignment has no rubric, so it cannot be graded. Add one from the Assignments page.</EmptyState>
    : <ErrorState error={ctx.error} onRetry={ctx.reload} />;
  const { assignment, rubric } = ctx.data;
  const criteria = [...rubric.criteria].sort((a, b) => a.sort_order - b.sort_order);
  const invalid = criteria.filter((c) => scores[c.id] === undefined || scores[c.id] === "" || Number(scores[c.id]) < 0 || Number(scores[c.id]) > Number(c.max_score));
  const unavailable = (submission.artifacts || []).filter((a) => a.availability_status !== "available").length;

  const post = async () => {
    setBusy(true); setError(null);
    try {
      const grade = await gradesApi.create({ submission_id: submission.id, scores: criteria.map((c) => ({ criterion_id: c.id, score: Number(scores[c.id]) })), feedback: feedback.trim() || null, apply_late_penalty: submission.is_late ? penalty : false });
      toast.success(`Graded ${submission.public_id}: final ${num(grade.final_score)}`);
      onGraded();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <Card title={`${submission.public_id} · ${assignmentTitle(submission.assignment_id)}`} actions={<>{submission.is_late ? <Badge tone="flag">Late</Badge> : <Badge tone="check">On time</Badge>}<Badge>v{submission.version_number}</Badge></>}>
        <p className="text-sm text-ink-700">{learnerName(submission.learner_id)} · submitted {dt(submission.submitted_at)} · due {dt(assignment.due_at)}</p>
        {unavailable > 0 && <div className="mt-2"><Notice tone="flag">{unavailable} artifact(s) are missing or quarantined.</Notice></div>}
        <div className="mt-3 overflow-hidden rounded-md border border-paper-200"><ArtifactTable artifacts={submission.artifacts} /></div>
      </Card>
      <Card title={`Rubric · ${rubric.name}`}>
        <Notice>{error}</Notice>
        <div className="mt-2 space-y-3">
          {criteria.map((c) => {
            const bad = invalid.includes(c) && scores[c.id] !== undefined && scores[c.id] !== "";
            return (
              <div key={c.id} className="grid items-start gap-2 sm:grid-cols-[1fr_10rem]">
                <div><p className="text-sm font-medium">{c.name}</p>{c.description && <p className="text-xs text-ink-500">{c.description}</p>}</div>
                <div>
                  <div className="flex items-center gap-2"><input type="number" min="0" max={c.max_score} step="0.01" aria-label={`Score for ${c.name}`} className="input" value={scores[c.id] ?? ""} onChange={(e) => setScores({ ...scores, [c.id]: e.target.value })} /><span className="whitespace-nowrap text-xs text-ink-500">/ {num(c.max_score)}</span></div>
                  {bad && <p className="mt-1 text-xs text-mark-700">Must be 0–{num(c.max_score)}</p>}
                </div>
              </div>
            );
          })}
        </div>
        {submission.is_late && (
          <label className="mt-4 flex items-start gap-2 rounded-md bg-flag-50 p-3 text-sm text-flag-500">
            <input type="checkbox" className="mt-0.5" checked={penalty} disabled={!assignment.allow_late} onChange={(e) => setPenalty(e.target.checked)} />
            <span>Apply the {Number(assignment.late_penalty_percent)}% late penalty (deducted from the raw score){!assignment.allow_late && ". Late work is not allowed for this assignment."}</span>
          </label>
        )}
        <div className="mt-4">
          <ScoreBreakdown criteria={criteria} scores={scores} latePercent={assignment.late_penalty_percent} applyPenalty={submission.is_late && penalty} isLate={submission.is_late} />
          <p className="mt-1 text-xs text-ink-500">Live preview. The server calculates the official result when you post.</p>
        </div>
        <Field label="Feedback to learner" className="mt-4"><textarea rows={3} className="input" value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="Optional comments" /></Field>
        <div className="mt-4 flex items-center justify-end gap-3">
          {invalid.length > 0 && <span className="text-xs text-ink-500">Enter a score for all {criteria.length} criteria</span>}
          <button className="btn-primary" disabled={busy || invalid.length > 0} onClick={post}>{busy ? "Posting…" : "Post grade"}</button>
        </div>
      </Card>
    </div>
  );
}

export default function Grading() {
  const { assignments, assignmentTitle, learnerName } = useLookups();
  const [params, setParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState(params.get("submission") ? Number(params.get("submission")) : null);
  const queue = usePaged(submissionsApi.list, { status: "submitted", assignment_id: "" }, { pageSize: 8 });
  // A deep link (?submission=ID) may not be on the current queue page, so load it directly.
  const deep = useApi(() => submissionsApi.get(selectedId), [selectedId], { enabled: Boolean(selectedId) });
  const selected = (queue.data?.items || []).find((s) => s.id === selectedId) || (deep.data?.id === selectedId ? deep.data : null);
  const pick = (id) => { setSelectedId(id); setParams(id ? { submission: id } : {}); };

  return (
    <>
      <PageHeader title="Grading workspace" subtitle="Score submissions against the rubric. The late penalty is shown step by step." />
      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <Card title={`Pending (${queue.data?.total ?? "…"})`} padded={false}>
          <div className="border-b border-paper-200 p-3">
            <select aria-label="Filter by assignment" className="input" value={queue.filters.assignment_id} onChange={(e) => queue.setFilters({ assignment_id: e.target.value })}><option value="">All assignments</option>{assignments.filter((a) => a.status !== "draft").map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}</select>
          </div>
          {queue.loading && !queue.data ? <Spinner /> : queue.error ? <div className="p-3"><ErrorState error={queue.error} onRetry={queue.reload} /></div> : !(queue.data?.items || []).length ? <div className="p-3"><EmptyState title="Queue is clear">No submissions are waiting to be graded.</EmptyState></div> : (
            <ul className="divide-y divide-paper-200">
              {queue.data.items.map((s) => (
                <li key={s.id}><button onClick={() => pick(s.id)} className={`w-full px-4 py-3 text-left text-sm hover:bg-paper-50 ${s.id === selectedId ? "bg-brand-50" : ""}`}>
                  <span className="flex items-center justify-between"><b>{learnerName(s.learner_id)}</b>{s.is_late && <Badge tone="flag">late</Badge>}</span>
                  <span className="block truncate text-xs text-ink-500">{assignmentTitle(s.assignment_id)} · v{s.version_number}</span>
                  <span className="block text-xs text-ink-500">{dt(s.submitted_at)}</span>
                </button></li>
              ))}
            </ul>
          )}
          <Pagination page={queue.page} pageSize={queue.pageSize} total={queue.data?.total} onPage={queue.setPage} />
        </Card>
        <div>
          {!selectedId ? <EmptyState title="Select a submission">Choose a submission from the queue to start grading.</EmptyState>
            : deep.loading && !selected ? <Spinner />
            : deep.error && !selected ? <ErrorState error={deep.error} onRetry={deep.reload} />
            : selected && selected.status !== "submitted" ? <EmptyState title="Already graded">{selected.public_id} is {selected.status}. Use Grades & feedback to revise it.</EmptyState>
            : selected ? <GradeForm submission={selected} onGraded={() => { pick(null); queue.reload(); }} /> : null}
        </div>
      </div>
    </>
  );
}

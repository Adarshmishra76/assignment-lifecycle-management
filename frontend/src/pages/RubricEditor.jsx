import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { assignmentsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Card, ErrorState, Field, Notice, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi } from "../hooks/useApi";
import { num, sumScores } from "../lib/format";

const blank = () => ({ key: Math.random().toString(36).slice(2), name: "", description: "", max_score: "10", weight: "1" });

export default function RubricEditor() {
  const { id } = useParams();
  const { role } = useAuth();
  const toast = useToast();
  const editable = can.manageAssignments(role);
  const assignment = useApi(() => assignmentsApi.get(id), [id]);
  // 404 just means "no rubric yet"; other errors are shown.
  const rubric = useApi(() => assignmentsApi.rubric(id).catch((e) => (e.status === 404 ? null : Promise.reject(e))), [id]);
  const [name, setName] = useState("Rubric");
  const [rows, setRows] = useState([blank()]);
  const [version, setVersion] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const r = rubric.data;
    if (!r) return;
    setName(r.name); setVersion(r.version_number);
    setRows([...r.criteria].sort((a, b) => a.sort_order - b.sort_order).map((c) => ({ key: String(c.id), name: c.name, description: c.description || "", max_score: String(Number(c.max_score)), weight: String(Number(c.weight)) })));
  }, [rubric.data]);

  const patch = (key, field, value) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, [field]: value } : r)));
  const move = (i, dir) => setRows((rs) => { const c = [...rs]; [c[i], c[i + dir]] = [c[i + dir], c[i]]; return c; });
  const total = sumScores(rows.map((r) => r.max_score));
  const names = rows.map((r) => r.name.trim().toLowerCase());
  const problems = [
    !name.trim() && "Rubric name is required.",
    rows.some((r) => !r.name.trim()) && "Every criterion needs a name.",
    names.some((n, i) => n && names.indexOf(n) !== i) && "Criterion names must be unique.",
    rows.some((r) => !(Number(r.max_score) > 0)) && "Every criterion needs a maximum score above zero.",
  ].filter(Boolean);

  const save = async () => {
    setBusy(true); setError(null);
    try {
      const saved = await assignmentsApi.saveRubric({ assignment_id: Number(id), name: name.trim(), criteria: rows.map((r, i) => ({ name: r.name.trim(), description: r.description || null, max_score: Number(r.max_score), weight: Number(r.weight) || 1, sort_order: i + 1 })) });
      setVersion(saved.version_number);
      toast.success(`Rubric saved (version ${saved.version_number})`);
      rubric.reload();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  if (assignment.loading || rubric.loading) return <Spinner />;
  if (assignment.error) return <ErrorState error={assignment.error} onRetry={assignment.reload} />;
  if (rubric.error) return <ErrorState error={rubric.error} onRetry={rubric.reload} />;
  const a = assignment.data;
  return (
    <>
      <Link to="/assignments" className="mb-3 inline-block text-sm text-ink-500 hover:text-ink-900">← Assignments</Link>
      <PageHeader title={`Rubric · ${a.title}`} subtitle={version ? `Saved version ${version}` : "No rubric yet. Define the grading criteria below."} actions={<StatusBadge status={a.status} />} />
      {a.status !== "draft" && editable && <div className="mb-4"><Notice tone="flag">This assignment is {a.status}. Saving bumps the rubric version.</Notice></div>}
      <Notice>{error}</Notice>
      <Card title="Criteria" className="mt-4">
        <div className="space-y-4">
          <Field label="Rubric name" className="max-w-md"><input className="input" value={name} disabled={!editable} onChange={(e) => setName(e.target.value)} /></Field>
          {rows.map((r, i) => (
            <div key={r.key} className="grid gap-3 rounded-md border border-paper-200 p-3 sm:grid-cols-[1fr_7rem_6rem_auto]">
              <div className="space-y-2">
                <input aria-label="Criterion name" className="input" placeholder="Criterion name" value={r.name} disabled={!editable} onChange={(e) => patch(r.key, "name", e.target.value)} />
                <input aria-label="Description" className="input" placeholder="Description (optional)" value={r.description} disabled={!editable} onChange={(e) => patch(r.key, "description", e.target.value)} />
              </div>
              <Field label="Max score"><input type="number" min="0" step="0.01" className="input" value={r.max_score} disabled={!editable} onChange={(e) => patch(r.key, "max_score", e.target.value)} /></Field>
              <Field label="Weight"><input type="number" min="0" step="0.001" className="input" value={r.weight} disabled={!editable} onChange={(e) => patch(r.key, "weight", e.target.value)} /></Field>
              {editable && (
                <div className="flex items-end gap-1 pb-1">
                  <button className="btn-quiet btn-sm" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move up">↑</button>
                  <button className="btn-quiet btn-sm" disabled={i === rows.length - 1} onClick={() => move(i, 1)} aria-label="Move down">↓</button>
                  <button className="btn-quiet btn-sm text-mark-500" disabled={rows.length === 1} onClick={() => setRows(rows.filter((x) => x.key !== r.key))} aria-label="Remove criterion">Remove</button>
                </div>
              )}
            </div>
          ))}
          <div className="flex flex-wrap items-end justify-between gap-3 border-t border-paper-200 pt-4">
            <div>
              <p className="text-sm text-ink-500">Rubric total (sum of max scores)</p>
              <p className="figure text-3xl">{num(total)}</p>
              <p className="text-xs text-ink-500">The raw grade is the plain sum of criterion scores. Weights are stored but do not change the total.</p>
            </div>
            {editable && (
              <div className="flex gap-2">
                <button className="btn-quiet" onClick={() => setRows([...rows, blank()])}>Add criterion</button>
                <button className="btn-primary" disabled={busy || problems.length > 0} onClick={save}>{busy ? "Saving…" : "Save rubric"}</button>
              </div>
            )}
          </div>
          {editable && problems.length > 0 && <ul className="list-disc pl-5 text-xs text-mark-700">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
        </div>
      </Card>
    </>
  );
}

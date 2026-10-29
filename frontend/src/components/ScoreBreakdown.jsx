import { num } from "../lib/format";
import { previewLatePenalty, sumScores } from "../lib/format";

/** Criterion scores -> raw total -> late penalty -> final. Pass `grade` for stored server values, or `scores` + `latePercent` for a live preview. */
export default function ScoreBreakdown({ criteria, scores, grade, latePercent, applyPenalty, isLate }) {
  const by = grade ? Object.fromEntries((grade.scores || []).map((s) => [s.criterion_id, s.score])) : scores || {};
  const max = sumScores(criteria.map((c) => c.max_score));
  const raw = grade ? Number(grade.raw_score) : sumScores(criteria.map((c) => by[c.id]));
  const preview = !grade && applyPenalty ? previewLatePenalty(raw, latePercent) : null;
  const applied = grade ? grade.late_penalty_applied : Boolean(preview);
  const penalty = grade ? Number(grade.late_penalty_amount) : preview ? preview.amount : 0;
  const final = grade ? Number(grade.final_score) : preview ? preview.final : raw;
  return (
    <table className="w-full overflow-hidden rounded-md border border-paper-200 text-sm">
      <thead className="bg-paper-50"><tr><th className="th">Criterion</th><th className="th text-right">Score</th><th className="th text-right">Max</th></tr></thead>
      <tbody className="divide-y divide-paper-200">
        {criteria.map((c) => (
          <tr key={c.id}><td className="td">{c.name}</td><td className="td text-right tabular-nums">{num(by[c.id] ?? 0)}</td><td className="td text-right tabular-nums text-ink-500">{num(c.max_score)}</td></tr>
        ))}
      </tbody>
      <tfoot className="bg-paper-50 tabular-nums">
        <tr className="font-medium"><td className="td">Raw total</td><td className="td text-right">{num(raw)}</td><td className="td text-right text-ink-500">{num(max)}</td></tr>
        <tr className={applied ? "text-mark-700" : "text-ink-500"}>
          <td className="td" colSpan={2}>Late penalty {applied ? (latePercent != null ? `(${Number(latePercent)}% of raw)` : "(applied)") : isLate ? "(not applied)" : "(on time)"}</td>
          <td className="td text-right">−{num(penalty)}</td>
        </tr>
        <tr className="border-t border-paper-200 text-base font-semibold"><td className="td" colSpan={2}>Final score</td><td className="td text-right">{num(final)}</td></tr>
      </tfoot>
    </table>
  );
}

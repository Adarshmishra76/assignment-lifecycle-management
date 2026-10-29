import { useState } from "react";
import { analyticsApi, datasetsApi, resubmissionsApi, submissionsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { ErrorState, PageHeader, RateBar, Spinner } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { days, int, label, num, pct } from "../lib/format";

// The checks the backend validator runs (backend/app/validators/engine.py). "Checks passing" is
// the share of these with zero findings, because the API reports counts, not records scanned.
const CHECKS = {
  unenrolled_submission: "Submission from an unenrolled learner",
  grade_exceeds_rubric_max: "Score above rubric maximum",
  duplicate_late_penalty: "Late penalty applied twice",
  appeal_grade_change_without_audit: "Appeal changed a grade with no audit event",
  deadline_mismatch: "Late flag disagrees with due date",
  fk_violation: "Broken reference",
  duplicate_public_id: "Duplicate public ID",
  invalid_enum: "Invalid status value",
  missing_rubric: "Grade without a rubric",
};

function Panel({ title, note, children }) {
  return (
    <section className="panel p-5">
      <h2 className="font-serif text-xl font-semibold">{title}</h2>
      {note && <p className="mt-0.5 text-sm text-ink-500">{note}</p>}
      <div className="mt-4 space-y-5">{children}</div>
    </section>
  );
}

function Fact({ name, value, hint }) {
  return (
    <div>
      <dt className="text-sm text-ink-500">{name}</dt>
      <dd className="figure text-2xl">{value}</dd>
      {hint && <p className="text-xs text-ink-500">{hint}</p>}
    </div>
  );
}

/** Score improvement is not in /analytics/overview, so measure it on a bounded sample of completed resubmissions. */
function ImprovementSample() {
  const [state, setState] = useState({ status: "idle" });
  const SAMPLE = 15;

  const measure = async () => {
    setState({ status: "loading" });
    try {
      const page = await resubmissionsApi.list({ page: 1, page_size: 100 });
      const done = page.items.filter((r) => r.status === "completed" && r.resulting_submission_id).slice(0, SAMPLE);
      const current = async (submissionId) => (await submissionsApi.grades(submissionId)).find((g) => g.is_current);
      const pairs = await Promise.all(
        done.map(async (r) => [await current(r.previous_submission_id), await current(r.resulting_submission_id)])
      );
      const valid = pairs.filter(([a, b]) => a && b);
      const deltas = valid.map(([a, b]) => Number(b.final_score) - Number(a.final_score));
      setState({
        status: "done",
        n: valid.length,
        mean: deltas.length ? deltas.reduce((s, x) => s + x, 0) / deltas.length : null,
        improved: deltas.filter((x) => x > 0).length,
      });
    } catch (error) {
      setState({ status: "error", error });
    }
  };

  if (state.status === "error") return <ErrorState error={state.error} onRetry={measure} />;
  if (state.status === "loading") return <Spinner label="Comparing graded resubmissions" />;
  if (state.status === "done") {
    return state.n ? (
      <Fact
        name="Average score change after resubmitting"
        value={`${state.mean >= 0 ? "+" : ""}${num(state.mean)} pts`}
        hint={`${state.improved} of ${state.n} graded resubmissions improved (sample of up to ${SAMPLE} from the latest 100 requests).`}
      />
    ) : (
      <p className="text-sm text-ink-500">No completed resubmissions have grades on both attempts yet.</p>
    );
  }
  return (
    <div>
      <p className="text-sm text-ink-500">Score improvement isn’t part of the overview, so it’s measured on a sample.</p>
      <button className="btn-quiet mt-2" onClick={measure}>Measure improvement</button>
    </div>
  );
}

function DataQuality() {
  const [state, setState] = useState(() => {
    try { return { status: "idle", report: JSON.parse(sessionStorage.getItem("alm_dq") || "null") }; }
    catch { return { status: "idle", report: null }; }
  });

  const run = async () => {
    setState((s) => ({ ...s, status: "loading", error: null }));
    try {
      const report = await datasetsApi.validate();
      try { sessionStorage.setItem("alm_dq", JSON.stringify({ ...report, findings: undefined, examples: undefined })); } catch { /* storage unavailable */ }
      setState({ status: "idle", report });
    } catch (error) {
      setState((s) => ({ ...s, status: "error", error }));
    }
  };

  const { report, status, error } = state;
  const total = Object.keys(CHECKS).length;
  const failing = report ? Object.keys(report.by_type || {}) : [];
  const passing = total - failing.filter((k) => k in CHECKS).length;

  return (
    <Panel title="Data quality" note="Runs every validator on the live database. Admin only; the run is recorded server-side.">
      <button className="btn-primary" onClick={run} disabled={status === "loading"}>
        {status === "loading" ? "Validating…" : report ? "Run validation again" : "Run validation"}
      </button>
      {status === "error" && <ErrorState error={error} onRetry={run} />}
      {report && (
        <>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
            <Fact name="Result" value={report.status === "pass" ? "Pass" : "Fail"} />
            <Fact name="Anomalies found" value={int(report.anomaly_count)} />
            <Fact name="Checks passing" value={`${passing} of ${total}`} hint={pct(passing / total, 0)} />
          </div>
          {failing.length === 0 ? (
            <p className="text-sm text-check-700">No anomalies detected.</p>
          ) : (
            <ul className="divide-y divide-paper-200 rounded-md border border-paper-200">
              {failing.map((k) => (
                <li key={k} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                  <span>{CHECKS[k] || label(k)}</span>
                  <span className="figure text-mark-700">{int(report.by_type[k])}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}

export default function Dashboard() {
  const { role } = useAuth();
  const { data: m, loading, error, reload } = useApi(analyticsApi.overview);

  if (loading && !m) return <Spinner label="Loading overview" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!m) return null;

  const count = (rate, total) => Math.round((rate || 0) * total);
  const late = count(m.late_rate, m.total_submissions);
  const penaltyGap = Number(m.average_raw_grade) - Number(m.average_final_grade);
  const outcomes = m.appeal_outcomes || {};
  const decided = (outcomes.approved || 0) + (outcomes.rejected || 0) + (outcomes.upheld || 0);
  const empty = m.total_submissions === 0;

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle={`${int(m.total_assignments)} assignments and ${int(m.total_submissions)} submissions across every course.`}
        actions={<button className="btn-quiet" onClick={reload} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>}
      />

      {empty && (
        <p className="mb-6 rounded-md border border-dashed border-ink-300 p-4 text-sm text-ink-500">
          No submissions yet, so every rate reads 0%. Generate a dataset from the Datasets page or wait for learners to submit.
        </p>
      )}

      <section className="panel mb-6 grid gap-6 p-6 sm:grid-cols-[1.4fr_1fr_1fr] sm:items-end">
        <div>
          <h2 className="text-sm font-medium text-ink-500">Waiting to be graded</h2>
          <p className="figure text-6xl">{int(m.pending_grading)}</p>
          <p className="mt-1 text-sm text-ink-500">
            {m.total_submissions ? `${pct(m.pending_grading / m.total_submissions)} of all submissions` : "No submissions yet"}
          </p>
        </div>
        <Fact name="Average grading turnaround" value={days(m.average_grading_turnaround_days)} hint="Submission to first grade" />
        <Fact name="Grade-change rate" value={pct(m.grade_change_rate)} hint="Revisions that replaced an earlier score, per submission" />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Timeliness and artifacts">
          <RateBar label="On time" tone="check" value={m.on_time_rate} display={pct(m.on_time_rate)}
            detail={`${int(m.total_submissions - late)} of ${int(m.total_submissions)} submissions`} />
          <RateBar label="Late" tone="flag" value={m.late_rate} display={pct(m.late_rate)}
            detail={`${int(late)} of ${int(m.total_submissions)} submissions`} />
          <RateBar label="Missing artifacts" tone="mark" value={m.missing_artifact_rate} display={pct(m.missing_artifact_rate)}
            detail="Share of uploaded files marked missing" />
        </Panel>

        <Panel title="Grades" note="Late penalties are the gap between raw and final.">
          <dl className="grid grid-cols-3 gap-4">
            <Fact name="Average raw" value={num(m.average_raw_grade)} />
            <Fact name="Average final" value={num(m.average_final_grade)} />
            <Fact name="Lost to penalties" value={num(penaltyGap)} hint="points on average" />
          </dl>
          <RateBar label="Final as share of raw" tone="brand"
            value={Number(m.average_raw_grade) ? Number(m.average_final_grade) / Number(m.average_raw_grade) : 0}
            display={pct(Number(m.average_raw_grade) ? Number(m.average_final_grade) / Number(m.average_raw_grade) : 0)}
            detail="Current grades only" />
        </Panel>

        <Panel title="Resubmissions">
          <RateBar label="Resubmission rate" tone="brand" value={m.resubmission_rate} display={pct(m.resubmission_rate)}
            detail="Resubmission requests per submission" />
          <ImprovementSample />
        </Panel>

        <Panel title="Appeals" note={decided ? `${int(decided)} decided` : "No appeals decided yet"}>
          <RateBar label="Appeal rate" tone="brand" value={m.appeal_rate} display={pct(m.appeal_rate)} detail="Appeals per submission" />
          {["approved", "upheld", "rejected"].map((k) => (
            <RateBar key={k} label={label(k)[0].toUpperCase() + label(k).slice(1)} tone={k === "approved" ? "check" : k === "upheld" ? "flag" : "mark"}
              value={decided ? (outcomes[k] || 0) / decided : 0} display={int(outcomes[k] || 0)}
              detail={decided ? `${pct((outcomes[k] || 0) / decided, 0)} of decided appeals` : undefined} />
          ))}
        </Panel>
      </div>

      {can.viewDataQuality(role) && (
        <div className="mt-6">
          <DataQuality />
        </div>
      )}
    </>
  );
}

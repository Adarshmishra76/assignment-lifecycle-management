import { Link, useNavigate, useParams } from "react-router-dom";
import { submissionsApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Badge, Card, DataTable, ErrorState, Field, FilterBar, PageHeader, Pagination, Spinner, StatusBadge } from "../components/ui";
import { useApi, usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { bytes, dt } from "../lib/format";
import { useState } from "react";

export const ArtifactSummary = ({ artifacts = [] }) => {
  const missing = artifacts.filter((a) => a.availability_status === "missing").length;
  const quarantined = artifacts.filter((a) => a.availability_status === "quarantined").length;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span>{artifacts.length} file{artifacts.length === 1 ? "" : "s"}</span>
      {missing > 0 && <Badge tone="mark">{missing} missing</Badge>}
      {quarantined > 0 && <Badge tone="flag">{quarantined} quarantined</Badge>}
    </span>
  );
};

export function ArtifactTable({ artifacts }) {
  return (
    <DataTable rows={artifacts} emptyTitle="No artifacts" emptyText="This version was submitted without files."
      columns={[
        { header: "File", render: (a) => <div><p className="font-medium">{a.filename}</p><p className="text-xs text-ink-500">{a.mime_type}</p></div> },
        { header: "Size", render: (a) => bytes(a.file_size_bytes) },
        { header: "SHA-256", render: (a) => <code title={a.checksum_sha256} className="text-xs text-ink-500">{a.checksum_sha256.slice(0, 12)}…{a.checksum_sha256.slice(-6)}</code> },
        { header: "Uploaded", render: (a) => dt(a.uploaded_at) },
        { header: "Availability", render: (a) => <StatusBadge status={a.availability_status} /> },
      ]} />
  );
}

/** Shared submission table, used by Submissions and Grades & feedback. */
export function SubmissionList({ title, subtitle, defaultStatus = "", statusOptions = ["", "submitted", "graded", "returned", "withdrawn"], linkTo = (s) => `/submissions/${s.id}`, emptyTitle = "No submissions found", emptyText = "Adjust the filters or check back later." }) {
  const { role } = useAuth();
  const { assignments, learners, assignmentTitle, learnerName } = useLookups();
  const navigate = useNavigate();
  const staff = can.viewLearners(role);
  const list = usePaged(submissionsApi.list, { assignment_id: "", learner_id: "", status: defaultStatus }, { pageSize: 10 });
  const [timing, setTiming] = useState("");
  const rows = (list.data?.items || []).filter((s) => !timing || (timing === "late" ? s.is_late : !s.is_late));
  const columns = [
    { header: "Submission", render: (s) => <span className="font-medium">{s.public_id}</span> },
    { header: "Assignment", render: (s) => assignmentTitle(s.assignment_id) },
    ...(staff ? [{ header: "Learner", render: (s) => learnerName(s.learner_id) }] : []),
    { header: "Version", render: (s) => `v${s.version_number}` },
    { header: "Submitted", render: (s) => dt(s.submitted_at) },
    { header: "Timing", render: (s) => (s.is_late ? <Badge tone="flag">Late</Badge> : <Badge tone="check">On time</Badge>) },
    { header: "Status", render: (s) => <StatusBadge status={s.status} /> },
    { header: "Artifacts", render: (s) => <ArtifactSummary artifacts={s.artifacts} /> },
  ];
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} />
      <Card padded={false}>
        <FilterBar>
          <Field label="Assignment" className="w-64"><select className="input" value={list.filters.assignment_id} onChange={(e) => list.setFilters({ assignment_id: e.target.value })}><option value="">All assignments</option>{assignments.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}</select></Field>
          {staff && <Field label="Learner" className="w-56"><select className="input" value={list.filters.learner_id} onChange={(e) => list.setFilters({ learner_id: e.target.value })}><option value="">All learners</option>{learners.map((l) => <option key={l.id} value={l.id}>{l.full_name}</option>)}</select></Field>}
          <Field label="Status" className="w-40"><select className="input" value={list.filters.status} onChange={(e) => list.setFilters({ status: e.target.value })}>{statusOptions.map((s) => <option key={s} value={s}>{s || "All"}</option>)}</select></Field>
          <Field label="Timing" className="w-36"><select className="input" value={timing} onChange={(e) => setTiming(e.target.value)}><option value="">All</option><option value="late">Late</option><option value="ontime">On time</option></select></Field>
        </FilterBar>
        <DataTable columns={columns} rows={rows} loading={list.loading} error={list.error} onRetry={list.reload} onRowClick={(s) => navigate(linkTo(s))} emptyTitle={emptyTitle} emptyText={emptyText} />
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      </Card>
    </>
  );
}

export default function Submissions() {
  const { role } = useAuth();
  return <SubmissionList title={can.viewLearners(role) ? "Submissions" : "My submissions"} subtitle="Every attempt with its artifacts. Select a row for the full version history." />;
}

export function SubmissionDetail() {
  const { id } = useParams();
  const { role } = useAuth();
  const { assignmentTitle, learnerName } = useLookups();
  const { data, loading, error, reload } = useApi(async () => {
    const submission = await submissionsApi.get(id);
    const all = await submissionsApi.list({ assignment_id: submission.assignment_id, learner_id: submission.learner_id, page_size: 100 });
    const versions = all.items.filter((s) => s.learner_id === submission.learner_id).sort((a, b) => a.version_number - b.version_number || new Date(a.submitted_at) - new Date(b.submitted_at));
    return { submission, versions };
  }, [id]);
  if (loading) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const { submission, versions } = data;
  return (
    <>
      <Link to="/submissions" className="mb-3 inline-block text-sm text-ink-500 hover:text-ink-900">← Submissions</Link>
      <PageHeader title={assignmentTitle(submission.assignment_id)} subtitle={`${can.viewLearners(role) ? `${learnerName(submission.learner_id)} · ` : ""}${versions.length} version${versions.length === 1 ? "" : "s"}, oldest first`} />
      <ol className="relative ml-3 space-y-5 border-l-2 border-paper-200 pl-6">
        {versions.map((v) => (
          <li key={v.id} className="relative">
            <span className={`absolute -left-[33px] top-4 h-3.5 w-3.5 rounded-full border-2 border-white ${v.id === submission.id ? "bg-brand-600" : "bg-ink-300"}`} />
            <Card padded={false}
              title={<span className="flex flex-wrap items-center gap-2">Version {v.version_number} <StatusBadge status={v.status} />{v.is_late ? <Badge tone="flag">Late</Badge> : <Badge tone="check">On time</Badge>}{v.id === submission.id && <Badge tone="brand">selected</Badge>}</span>}
              actions={<><span className="text-xs text-ink-500">{v.public_id} · {dt(v.submitted_at)}</span>
                {["graded", "returned"].includes(v.status) && <Link className="btn-quiet btn-sm" to={`/grades/${v.id}`}>Grade history</Link>}
                {v.status === "submitted" && can.grade(role) && <Link className="btn-primary btn-sm" to={`/grading?submission=${v.id}`}>Grade</Link>}</>}>
              <ArtifactTable artifacts={v.artifacts} />
            </Card>
          </li>
        ))}
      </ol>
    </>
  );
}

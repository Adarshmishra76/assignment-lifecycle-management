import { useState } from "react";
import { coursesApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Card, DataTable, Field, FilterBar, Modal, Notice, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { useToast } from "../components/Toast";
import { usePaged } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { d, dt } from "../lib/format";

function CourseModal({ course, role, onClose, onSaved }) {
  const toast = useToast();
  const editing = Boolean(course);
  const [form, setForm] = useState(editing ? { title: course.title, term: course.term, description: course.description || "", status: course.status } : { code: "", title: "", term: "", description: "", instructor_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    setBusy(true); setError(null);
    try {
      if (editing) await coursesApi.update(course.id, form);
      else await coursesApi.create({ ...form, instructor_id: form.instructor_id ? Number(form.instructor_id) : null });
      toast.success(editing ? "Course updated" : "Course created");
      onSaved();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal title={editing ? `Edit ${course.code}` : "New course"} onClose={onClose}
      footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || !form.title || !form.term || (!editing && !form.code)} onClick={save}>{busy ? "Saving…" : "Save"}</button></>}>
      <div className="space-y-4">
        <Notice>{error}</Notice>
        {!editing && <Field label="Code"><input className="input" value={form.code} onChange={set("code")} placeholder="CS101" /></Field>}
        <Field label="Title"><input className="input" value={form.title} onChange={set("title")} /></Field>
        <Field label="Term"><input className="input" value={form.term} onChange={set("term")} placeholder="2026-Fall" /></Field>
        <Field label="Description"><textarea rows={3} className="input" value={form.description} onChange={set("description")} /></Field>
        {editing && <Field label="Status"><select className="input" value={form.status} onChange={set("status")}><option>draft</option><option>active</option><option>archived</option></select></Field>}
        {!editing && role !== "instructor" && <Field label="Instructor user ID" hint="Leave blank to assign yourself"><input type="number" min="1" className="input" value={form.instructor_id} onChange={set("instructor_id")} /></Field>}
      </div>
    </Modal>
  );
}

function EnrollModal({ onClose, onSaved }) {
  const { courses, learners } = useLookups();
  const toast = useToast();
  const [form, setForm] = useState({ course_id: "", learner_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const save = async () => {
    setBusy(true); setError(null);
    try { await coursesApi.enroll({ course_id: Number(form.course_id), learner_id: Number(form.learner_id) }); toast.success("Learner enrolled"); onSaved(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal title="Enroll learner" onClose={onClose} footer={<><button className="btn-quiet" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy || !form.course_id || !form.learner_id} onClick={save}>{busy ? "Enrolling…" : "Enroll"}</button></>}>
      <div className="space-y-4">
        <Notice>{error}</Notice>
        <Field label="Course"><select className="input" value={form.course_id} onChange={(e) => setForm({ ...form, course_id: e.target.value })}><option value="">Select a course…</option>{courses.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}</select></Field>
        <Field label="Learner" hint="The first 100 learners are listed"><select className="input" value={form.learner_id} onChange={(e) => setForm({ ...form, learner_id: e.target.value })}><option value="">Select a learner…</option>{learners.map((l) => <option key={l.id} value={l.id}>{l.full_name} ({l.student_number})</option>)}</select></Field>
      </div>
    </Modal>
  );
}

function CoursesTab({ role }) {
  const lookups = useLookups();
  const list = usePaged(coursesApi.list, {}, { pageSize: 10 });
  const [modal, setModal] = useState(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  // The API has no search/status filter for courses, so these narrow the current page.
  const rows = (list.data?.items || []).filter((c) => (!status || c.status === status) && (!search || `${c.code} ${c.title} ${c.term}`.toLowerCase().includes(search.toLowerCase())));
  const columns = [
    { header: "Code", render: (c) => <span className="font-medium">{c.code}</span> },
    { header: "Title", key: "title" },
    { header: "Term", key: "term" },
    { header: "Status", render: (c) => <StatusBadge status={c.status} /> },
    { header: "Instructor", render: (c) => `User #${c.instructor_id}` },
    { header: "Created", render: (c) => d(c.created_at) },
    ...(can.createCourse(role) ? [{ header: "", render: (c) => <button className="btn-quiet btn-sm" onClick={() => setModal({ course: c })}>Edit</button> }] : []),
  ];
  return (
    <Card padded={false}>
      <FilterBar>
        <Field label="Search" className="w-56"><input className="input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Code, title, term" /></Field>
        <Field label="Status" className="w-40"><select className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option><option>draft</option><option>active</option><option>archived</option></select></Field>
        <span className="pb-2 text-xs text-ink-500">Filters apply to the current page.</span>
        {can.createCourse(role) && <button className="btn-primary ml-auto" onClick={() => setModal({})}>New course</button>}
      </FilterBar>
      <DataTable columns={columns} rows={rows} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No courses" emptyText={can.createCourse(role) ? "Create the first course to get started." : "You are not enrolled in any courses yet."} />
      <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      {modal && <CourseModal course={modal.course} role={role} onClose={() => setModal(null)} onSaved={() => { setModal(null); list.reload(); lookups.refresh(); }} />}
    </Card>
  );
}

function EnrollmentsTab({ role }) {
  const { courses, courseName, learnerName } = useLookups();
  const list = usePaged(coursesApi.enrollments, { course_id: "" }, { pageSize: 10 });
  const [open, setOpen] = useState(false);
  const columns = [
    { header: "Learner", render: (e) => learnerName(e.learner_id) },
    { header: "Course", render: (e) => courseName(e.course_id) },
    { header: "Status", render: (e) => <StatusBadge status={e.status} /> },
    { header: "Enrolled", render: (e) => dt(e.enrolled_at) },
  ];
  return (
    <Card padded={false}>
      <FilterBar>
        <Field label="Course" className="w-64"><select className="input" value={list.filters.course_id} onChange={(e) => list.setFilters({ course_id: e.target.value })}><option value="">All courses</option>{courses.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}</select></Field>
        {can.enroll(role) && <button className="btn-primary ml-auto" onClick={() => setOpen(true)}>Enroll learner</button>}
      </FilterBar>
      <DataTable columns={columns} rows={list.data?.items} loading={list.loading} error={list.error} onRetry={list.reload} emptyTitle="No enrollments" emptyText="Enroll learners so they can submit work." />
      <Pagination page={list.page} pageSize={list.pageSize} total={list.data?.total} onPage={list.setPage} />
      {open && <EnrollModal onClose={() => setOpen(false)} onSaved={() => { setOpen(false); list.reload(); }} />}
    </Card>
  );
}

export default function Courses() {
  const { role } = useAuth();
  const [tab, setTab] = useState("courses");
  const tabs = [["courses", "Courses"], ...(can.viewLearners(role) ? [["enrollments", "Enrollments"]] : [])];
  return (
    <>
      <PageHeader title="Courses & enrollments" subtitle="Manage courses and who is enrolled in them." />
      {tabs.length > 1 && (
        <div className="mb-4 flex gap-1 border-b border-paper-200">
          {tabs.map(([id, label]) => <button key={id} onClick={() => setTab(id)} className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${tab === id ? "border-brand-600 text-brand-700" : "border-transparent text-ink-500 hover:text-ink-900"}`}>{label}</button>)}
        </div>
      )}
      {tab === "courses" ? <CoursesTab role={role} /> : <EnrollmentsTab role={role} />}
    </>
  );
}

// UI-only capability map. It mirrors backend/app/services/access.py so we can HIDE
// actions a role cannot perform. The server remains the source of truth and still
// rejects anything unauthorized (403), which the UI surfaces as an error message.
export const ROLES = {
  learner: "Learner",
  instructor: "Instructor",
  academic_admin: "Academic administrator",
  support_staff: "Support staff",
  platform_admin: "Platform administrator",
};

const STAFF = ["instructor", "academic_admin", "support_staff", "platform_admin"];
const GRADERS = ["instructor", "academic_admin", "platform_admin"];
const ADMINS = ["academic_admin", "platform_admin"];

export const can = {
  viewDashboard: (r) => STAFF.includes(r),
  createCourse: (r) => [...ADMINS, "instructor"].includes(r),
  enroll: (r) => [...ADMINS, "instructor", "support_staff"].includes(r),
  createLearner: (r) => [...ADMINS, "support_staff"].includes(r),
  viewLearners: (r) => STAFF.includes(r),
  manageAssignments: (r) => GRADERS.includes(r),
  grade: (r) => GRADERS.includes(r),
  submitWork: (r) => r === "learner",
  requestResubmission: (r) => r === "learner",
  decideResubmission: (r) => GRADERS.includes(r),
  fileAppeal: (r) => r === "learner",
  reviewAppeal: (r) => GRADERS.includes(r),
  viewAudit: (r) => STAFF.includes(r),
  viewDataQuality: (r) => ADMINS.includes(r),
  manageDatasets: (r) => ADMINS.includes(r),
  generateDataset: (r) => r === "platform_admin",
};

// Navigation. `show` decides role visibility; routes are also guarded in App.jsx.
export const NAV = [
  { to: "/", label: "Overview", show: can.viewDashboard },
  { to: "/courses", label: "Courses & enrollments", show: () => true },
  { to: "/learners", label: "Learners", show: can.viewLearners },
  { to: "/assignments", label: "Assignments", show: can.manageAssignments },
  { to: "/my-assignments", label: "My assignments", show: (r) => r === "learner" },
  { to: "/submissions", label: "Submissions", show: () => true },
  { to: "/grading", label: "Grading workspace", show: can.grade },
  { to: "/grades", label: "Grades & feedback", show: () => true },
  { to: "/resubmissions", label: "Resubmissions", show: () => true },
  { to: "/appeals", label: "Appeals", show: () => true },
  { to: "/audit", label: "Audit trail", show: can.viewAudit },
  { to: "/datasets", label: "Datasets & export", show: can.manageDatasets },
  { to: "/data-quality", label: "Data quality", show: can.viewDataQuality },
];

export const homeFor = (role) => (can.viewDashboard(role) ? "/" : "/my-assignments");

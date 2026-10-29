import { get, post, patch } from "./client";

export const authApi = {
  login: (email, password) => post("/auth/login", { email, password }),
  me: () => get("/auth/me"),
  register: (body) => post("/auth/register", body),
};

export const analyticsApi = {
  overview: () => get("/analytics/overview"),
};

export const coursesApi = {
  list: (params) => get("/courses", params),
  create: (body) => post("/courses", body),
  update: (id, body) => patch(`/courses/${id}`, body),
  enrollments: (params) => get("/courses/enrollments", params),
  enroll: (body) => post("/courses/enrollments", body),
};

export const learnersApi = {
  list: (params) => get("/learners", params),
  create: (body) => post("/learners", body),
};

export const assignmentsApi = {
  list: (params) => get("/assignments", params),
  get: (id) => get(`/assignments/${id}`),
  create: (body) => post("/assignments", body),
  update: (id, body) => patch(`/assignments/${id}`, body),
  publish: (id) => post(`/assignments/${id}/publish`),
  versions: (id) => get(`/assignments/${id}/versions`),
  rubric: (id) => get(`/assignments/${id}/rubric`),
  saveRubric: (body) => post("/assignments/rubrics", body),
};

export const submissionsApi = {
  list: (params) => get("/submissions", params),
  get: (id) => get(`/submissions/${id}`),
  create: (body) => post("/submissions", body),
  grades: (id) => get(`/submissions/${id}/grades`),
  feedback: (id) => get(`/submissions/${id}/feedback`),
  revisions: (id) => get(`/submissions/${id}/revisions`),
};

export const gradesApi = {
  get: (id) => get(`/grades/${id}`),
  create: (body) => post("/grades", body),
  revise: (id, body) => post(`/grades/${id}/revise`, body),
};

export const resubmissionsApi = {
  list: (params) => get("/resubmissions", params),
  request: (body) => post("/resubmissions", body),
  decide: (id, body) => post(`/resubmissions/${id}/decision`, body),
  submit: (id, body) => post(`/resubmissions/${id}/submit`, body),
};

export const appealsApi = {
  list: (params) => get("/appeals", params),
  create: (body) => post("/appeals", body),
  review: (id) => post(`/appeals/${id}/review`),
  decide: (id, body) => post(`/appeals/${id}/decision`, body),
};

export const auditApi = { list: (params) => get("/audit-events", params) };

export const datasetsApi = {
  generate: (body) => post("/datasets/generate", body),
  validate: () => post("/datasets/validate"),
  exports: () => get("/datasets/exports"),
  exportPath: (mode, filename) => `/datasets/exports/${mode}/${filename}`,
};

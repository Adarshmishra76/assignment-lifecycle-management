import { describe, expect, it } from "vitest";
import { NAV, ROLES, can, homeFor } from "./permissions";

const roles = Object.keys(ROLES);

// capability -> roles that must have it (mirrors backend/app/services/access.py)
const EXPECTED = {
  viewDashboard: ["instructor", "academic_admin", "support_staff", "platform_admin"],
  createCourse: ["instructor", "academic_admin", "platform_admin"],
  enroll: ["instructor", "academic_admin", "support_staff", "platform_admin"],
  createLearner: ["academic_admin", "support_staff", "platform_admin"],
  viewLearners: ["instructor", "academic_admin", "support_staff", "platform_admin"],
  manageAssignments: ["instructor", "academic_admin", "platform_admin"],
  grade: ["instructor", "academic_admin", "platform_admin"],
  submitWork: ["learner"],
  requestResubmission: ["learner"],
  decideResubmission: ["instructor", "academic_admin", "platform_admin"],
  fileAppeal: ["learner"],
  reviewAppeal: ["instructor", "academic_admin", "platform_admin"],
  viewAudit: ["instructor", "academic_admin", "support_staff", "platform_admin"],
  viewDataQuality: ["academic_admin", "platform_admin"],
  manageDatasets: ["academic_admin", "platform_admin"],
  generateDataset: ["platform_admin"],
};

describe("capability map", () => {
  it("covers every capability the table above lists", () => {
    expect(Object.keys(can).sort()).toEqual(Object.keys(EXPECTED).sort());
  });

  for (const [capability, allowed] of Object.entries(EXPECTED)) {
    it(`${capability} is granted to exactly: ${allowed.join(", ")}`, () => {
      expect(roles.filter((role) => can[capability](role))).toEqual(roles.filter((r) => allowed.includes(r)));
    });
  }

  it("never grants anything to an unknown or missing role", () => {
    for (const fn of Object.values(can)) {
      expect(fn("visitor")).toBe(false);
      expect(fn(undefined)).toBe(false);
    }
  });

  it("support staff can look but not grade or decide", () => {
    expect(can.viewLearners("support_staff")).toBe(true);
    expect(can.grade("support_staff")).toBe(false);
    expect(can.reviewAppeal("support_staff")).toBe(false);
  });
});

describe("navigation", () => {
  const visible = (role) => NAV.filter((item) => item.show(role)).map((item) => item.to);

  it("shows a learner only their own workflow", () => {
    expect(visible("learner")).toEqual([
      "/courses",
      "/my-assignments",
      "/submissions",
      "/grades",
      "/resubmissions",
      "/appeals",
    ]);
  });

  it("hides admin screens from instructors", () => {
    const items = visible("instructor");
    expect(items).toContain("/grading");
    expect(items).not.toContain("/datasets");
    expect(items).not.toContain("/data-quality");
    expect(items).not.toContain("/my-assignments");
  });

  it("shows every screen except the learner one to a platform administrator", () => {
    expect(visible("platform_admin")).toEqual(NAV.map((i) => i.to).filter((to) => to !== "/my-assignments"));
  });

  it("has unique routes", () => {
    const routes = NAV.map((item) => item.to);
    expect(new Set(routes).size).toBe(routes.length);
  });
});

describe("homeFor", () => {
  it("sends staff to the dashboard and learners to their assignments", () => {
    expect(homeFor("instructor")).toBe("/");
    expect(homeFor("support_staff")).toBe("/");
    expect(homeFor("learner")).toBe("/my-assignments");
  });
});

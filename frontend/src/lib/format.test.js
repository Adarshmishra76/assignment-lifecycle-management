import { describe, expect, it } from "vitest";
import {
  bytes,
  days,
  int,
  label,
  num,
  pct,
  previewLatePenalty,
  signed,
  sortByDate,
  sumScores,
  toIso,
  toLocalInput,
} from "./format";

describe("formatters", () => {
  it("shows an em dash for missing values", () => {
    expect(pct(null)).toBe("—");
    expect(num(undefined)).toBe("—");
    expect(num("abc")).toBe("—");
    expect(int(null)).toBe("—");
    expect(label("")).toBe("—");
    expect(days(null)).toBe("—");
  });

  it("formats numbers", () => {
    expect(pct(0.1234)).toBe("12.3%");
    expect(pct(0.5, 0)).toBe("50%");
    expect(num("72")).toBe("72.00");
    expect(num(8.005, 1)).toBe("8.0");
    expect(label("under_review")).toBe("under review");
    expect(days(0.5)).toBe("12.0 h");
    expect(days(3)).toBe("3.0 days");
    expect(signed(2)).toBe("+2.00");
    expect(signed(-1.5)).toBe("−1.50");
    expect(signed(0)).toBe("+0.00");
  });

  it("formats file sizes", () => {
    expect(bytes(512)).toBe("512 B");
    expect(bytes(2048)).toBe("2.0 KB");
    expect(bytes(5 * 1048576)).toBe("5.0 MB");
    expect(bytes(undefined)).toBe("0 B");
  });

  it("sorts rows chronologically without mutating the input", () => {
    const rows = [{ at: "2026-03-01" }, { at: "2026-01-01" }, { at: "2026-02-01" }];
    expect(sortByDate(rows, "at").map((r) => r.at)).toEqual(["2026-01-01", "2026-02-01", "2026-03-01"]);
    expect(rows[0].at).toBe("2026-03-01");
  });
});

describe("score maths", () => {
  it("sums decimals without floating-point drift", () => {
    expect(sumScores([0.1, 0.2])).toBe(0.3);
    expect(sumScores(["10.005", 10])).toBe(20.01);
    expect(sumScores(["x", 5, undefined])).toBe(5);
    expect(sumScores([])).toBe(0);
  });

  // The same rows are asserted against apply_late_penalty() in backend/tests/test_lifecycle_rules.py.
  it.each([
    [80, 10, 8, 72],
    [33.33, 10, 3.33, 30],
    [59.95, 15, 8.99, 50.96],
    [100, 0, 0, 100],
    [100, 100, 100, 0],
    [0, 10, 0, 0],
    [0.05, 10, 0.01, 0.04], // half-up: 0.005 rounds to 0.01
  ])("previewLatePenalty(%s, %s%%) -> penalty %s, final %s", (raw, percent, amount, final) => {
    expect(previewLatePenalty(raw, percent)).toEqual({ amount, final });
  });

  it("never previews a negative final score", () => {
    expect(previewLatePenalty(50, 250).final).toBe(0);
  });

  it("applies the penalty to the raw score once", () => {
    const { final } = previewLatePenalty(80, 10);
    expect(final).toBe(72); // 80 - 10% of 80, not 80 - 8 - 7.2
  });
});

describe("date inputs", () => {
  it("round-trips a datetime-local value", () => {
    expect(toLocalInput(toIso("2026-03-04T05:06"))).toBe("2026-03-04T05:06");
  });

  it("handles empty values", () => {
    expect(toIso("")).toBeNull();
    expect(toLocalInput(null)).toBe("");
  });
});

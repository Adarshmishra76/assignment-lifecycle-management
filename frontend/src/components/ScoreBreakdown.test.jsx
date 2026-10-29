import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ScoreBreakdown from "./ScoreBreakdown";

const criteria = [
  { id: 1, name: "Correctness", max_score: "60.00" },
  { id: 2, name: "Style", max_score: "40.00" },
];

const rowOf = (text) => screen.getByText(text).closest("tr");

describe("ScoreBreakdown with a stored grade", () => {
  const lateGrade = {
    scores: [
      { criterion_id: 1, score: "50.00" },
      { criterion_id: 2, score: "30.00" },
    ],
    raw_score: "80.00",
    late_penalty_applied: true,
    late_penalty_amount: "8.00",
    final_score: "72.00",
  };

  it("shows each criterion, the raw total, the penalty and the final score", () => {
    render(<ScoreBreakdown criteria={criteria} grade={lateGrade} latePercent="10.00" isLate />);

    expect(within(rowOf("Correctness")).getByText("50.00")).toBeInTheDocument();
    expect(within(rowOf("Correctness")).getByText("60.00")).toBeInTheDocument();
    expect(within(rowOf("Style")).getByText("30.00")).toBeInTheDocument();

    const raw = rowOf("Raw total");
    expect(within(raw).getByText("80.00")).toBeInTheDocument();
    expect(within(raw).getByText("100.00")).toBeInTheDocument();

    expect(screen.getByText(/Late penalty \(10% of raw\)/)).toBeInTheDocument();
    expect(within(screen.getByText(/Late penalty/).closest("tr")).getByText("−8.00")).toBeInTheDocument();
    expect(within(rowOf("Final score")).getByText("72.00")).toBeInTheDocument();
  });

  it("labels an on-time submission as such", () => {
    const grade = { ...lateGrade, late_penalty_applied: false, late_penalty_amount: "0.00", final_score: "80.00" };
    render(<ScoreBreakdown criteria={criteria} grade={grade} isLate={false} />);
    expect(screen.getByText(/Late penalty \(on time\)/)).toBeInTheDocument();
    expect(within(rowOf("Final score")).getByText("80.00")).toBeInTheDocument();
  });

  it("says when a late penalty was waived", () => {
    const grade = { ...lateGrade, late_penalty_applied: false, late_penalty_amount: "0.00", final_score: "80.00" };
    render(<ScoreBreakdown criteria={criteria} grade={grade} isLate />);
    expect(screen.getByText(/Late penalty \(not applied\)/)).toBeInTheDocument();
  });

  it("uses the server's numbers rather than recomputing them", () => {
    const grade = { ...lateGrade, final_score: "71.50" };
    render(<ScoreBreakdown criteria={criteria} grade={grade} latePercent="10.00" isLate />);
    expect(within(rowOf("Final score")).getByText("71.50")).toBeInTheDocument();
  });
});

describe("ScoreBreakdown live preview", () => {
  it("previews the penalty as a percentage of the raw score", () => {
    render(<ScoreBreakdown criteria={criteria} scores={{ 1: 50, 2: 30 }} latePercent="10" applyPenalty isLate />);
    expect(within(rowOf("Raw total")).getByText("80.00")).toBeInTheDocument();
    expect(within(screen.getByText(/Late penalty/).closest("tr")).getByText("−8.00")).toBeInTheDocument();
    expect(within(rowOf("Final score")).getByText("72.00")).toBeInTheDocument();
  });

  it("leaves the raw score alone when no penalty applies", () => {
    render(<ScoreBreakdown criteria={criteria} scores={{ 1: 55, 2: 35 }} applyPenalty={false} isLate={false} />);
    expect(within(rowOf("Final score")).getByText("90.00")).toBeInTheDocument();
  });

  it("treats unscored criteria as zero", () => {
    render(<ScoreBreakdown criteria={criteria} scores={{ 1: 20 }} applyPenalty={false} />);
    expect(within(rowOf("Raw total")).getByText("20.00")).toBeInTheDocument();
    expect(within(rowOf("Style")).getByText("0.00")).toBeInTheDocument();
  });
});

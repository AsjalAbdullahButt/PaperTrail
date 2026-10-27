import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ConfidenceGauge from "./ConfidenceGauge";

describe("ConfidenceGauge", () => {
  it("shows a low-confidence label and tooltip below 0.4", () => {
    const { container } = render(<ConfidenceGauge value={0.2} />);
    expect(screen.getByText("Low confidence")).toBeInTheDocument();
    expect(container.querySelector("[title]")).toHaveAttribute(
      "title",
      "Low — answer may not be in documents"
    );
  });

  it("shows a moderate-confidence label and tooltip between 0.4 and 0.7", () => {
    const { container } = render(<ConfidenceGauge value={0.55} />);
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(container.querySelector("[title]")).toHaveAttribute(
      "title",
      "Moderate — review sources"
    );
  });

  it("shows a high-confidence label and tooltip above 0.7", () => {
    const { container } = render(<ConfidenceGauge value={0.85} />);
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(container.querySelector("[title]")).toHaveAttribute(
      "title",
      "High — well-supported"
    );
  });

  it("clamps out-of-range values into 0..100%", () => {
    render(<ConfidenceGauge value={1.5} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});

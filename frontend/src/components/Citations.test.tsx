import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderAnswerWithCitations } from "@/components/Citations";

describe("renderAnswerWithCitations", () => {
  it("renders an in-range [n] token as a citation link to the source", () => {
    render(<div>{renderAnswerWithCitations("See [1] and [2].", 2)}</div>);
    const link = screen.getByRole("link", { name: /citation 1/i });
    expect(link).toHaveAttribute("href", "#src-1");
    expect(screen.getByRole("link", { name: /citation 2/i })).toBeInTheDocument();
  });

  it("leaves an out-of-range [n] token as plain text (no link)", () => {
    const { container } = render(
      <div>{renderAnswerWithCitations("Ref [9] is missing", 2)}</div>
    );
    expect(screen.queryByRole("link")).toBeNull();
    expect(container.textContent).toContain("[9]");
  });

  it("renders answers without citations verbatim", () => {
    const { container } = render(
      <div>{renderAnswerWithCitations("Plain answer.", 0)}</div>
    );
    expect(container.textContent).toBe("Plain answer.");
  });
});

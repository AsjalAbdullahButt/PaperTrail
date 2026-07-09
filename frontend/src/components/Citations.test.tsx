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

  it("renders ## headings as real elements, not literal hashes", () => {
    const { container } = render(
      <div>{renderAnswerWithCitations("## Section One\nSome body text.", 0)}</div>
    );
    expect(screen.getByText("Section One").tagName).toBe("DIV");
    expect(container.textContent).not.toContain("##");
    expect(container.textContent).toContain("Some body text.");
  });

  it("renders **bold** as <strong>, stripping the asterisks", () => {
    render(<div>{renderAnswerWithCitations("This is **important** text.", 0)}</div>);
    const strong = screen.getByText("important");
    expect(strong.tagName).toBe("STRONG");
  });

  it("renders '- ' lines as a real list", () => {
    const { container } = render(
      <div>{renderAnswerWithCitations("- First step\n- Second step", 0)}</div>
    );
    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("First step");
    expect(items[1].textContent).toBe("Second step");
  });

  it("still resolves citation chips inside bold text and list items", () => {
    render(
      <div>
        {renderAnswerWithCitations("**Key fact** [1]\n- Detail [2]", 2)}
      </div>
    );
    expect(screen.getByRole("link", { name: /citation 1/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /citation 2/i })).toBeInTheDocument();
  });
});

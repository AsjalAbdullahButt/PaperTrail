import { describe, it, expect } from "vitest";
import { passwordComplexityError, passwordRules } from "./PasswordField";

describe("passwordComplexityError", () => {
  it("rejects passwords under 8 characters", () => {
    expect(passwordComplexityError("ab1")).toMatch(/at least 8 characters/i);
  });

  it("rejects passwords missing a letter", () => {
    expect(passwordComplexityError("12345678")).toMatch(/letter and one number/i);
  });

  it("rejects passwords missing a number", () => {
    expect(passwordComplexityError("abcdefgh")).toMatch(/letter and one number/i);
  });

  it("accepts a password meeting every server-side rule", () => {
    expect(passwordComplexityError("password1")).toBeNull();
  });
});

describe("passwordRules", () => {
  it("reports each rule's pass/fail state independently", () => {
    const rules = passwordRules("short1");
    expect(rules.find((r) => r.label.includes("8 characters"))?.met).toBe(false);
    expect(rules.find((r) => r.label.includes("letter"))?.met).toBe(true);
    expect(rules.find((r) => r.label.includes("number"))?.met).toBe(true);
  });
});

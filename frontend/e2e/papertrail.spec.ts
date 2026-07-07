import { test, expect } from "@playwright/test";

/**
 * Full happy path: register -> upload -> ask -> see citations -> open the
 * document manager -> delete -> confirm the document is gone from the list
 * (and, via the backend, from future answers).
 *
 * Requires a live backend at http://localhost:8000 with MySQL. Not run in the
 * sandbox (no browser/servers); intended for local/CI with services up.
 */
test("upload, ask, cite, then delete removes the document", async ({ page }) => {
  const email = `e2e-${Date.now()}@papertrail.io`;

  await page.goto("/");

  // Register a fresh user.
  await page.getByRole("button", { name: /create one/i }).click();
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /create account/i }).click();

  // Land on the app.
  await expect(page.getByRole("button", { name: /upload document/i })).toBeVisible();

  // Upload a text document with distinctive content.
  await page.setInputFiles('input[type="file"]', {
    name: "moonstone.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "The moonstone cipher key is amber-lantern-42, a unique phrase."
    ),
  });
  await expect(page.getByText(/uploaded moonstone\.txt/i)).toBeVisible();

  // Ask a question grounded in the document.
  await page
    .getByRole("textbox", { name: /ask a question/i })
    .fill("What is the moonstone cipher key?");
  await page.getByRole("button", { name: /^ask$/i }).click();

  // A citation chip appears and links to a source.
  const citation = page.getByRole("link", { name: /citation 1/i });
  await expect(citation).toBeVisible();

  // Open the document manager and delete the document.
  await page.getByRole("button", { name: /^documents$/i }).click();
  await expect(page.getByText("moonstone.txt")).toBeVisible();
  await page.getByRole("button", { name: /delete moonstone\.txt/i }).click();
  await page.getByRole("button", { name: /^confirm$/i }).click();

  // It disappears from the list.
  await expect(page.getByText("moonstone.txt")).toHaveCount(0);
});

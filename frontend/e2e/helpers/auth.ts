import { type Page, expect } from "@playwright/test";

/**
 * Default test credentials.
 * These match the password policy (SEC-04): 8+ chars, upper, lower, digit, special.
 * Adjust email/password if the seed data uses different values.
 */
export const TEST_EMAIL = "admin@test.com";
export const TEST_PASSWORD = "Test@pass123";

/**
 * Perform a full login via the UI.
 *
 * Navigates to /login, fills the form, submits, and waits for the redirect
 * to /dashboard. Throws if the login form shows an error or the redirect
 * does not happen within the timeout.
 */
export async function login(
  page: Page,
  email: string = TEST_EMAIL,
  password: string = TEST_PASSWORD,
): Promise<void> {
  await page.goto("/login");

  // Wait for the login form to be ready (the "Sign in" button)
  await page.waitForSelector('button[type="submit"]', { state: "visible" });

  // Fill credentials using the input IDs from the login page source
  await page.fill("#email", email);
  await page.fill("#password", password);

  // Submit the form
  await page.click('button[type="submit"]');

  // Wait for successful redirect to /dashboard
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

/**
 * Assert the page has been redirected to the login page.
 * Useful for verifying protected route enforcement.
 */
export async function expectRedirectToLogin(page: Page): Promise<void> {
  await expect(page).toHaveURL(/\/login/);
}

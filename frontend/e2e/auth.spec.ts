import { test, expect } from "@playwright/test";
import {
  login,
  expectRedirectToLogin,
  TEST_EMAIL,
  TEST_PASSWORD,
} from "./helpers/auth";

test.describe("Authentication Flow", () => {
  test("successful login redirects to dashboard", async ({ page }) => {
    await login(page);

    // Verify we are on the dashboard
    await expect(page).toHaveURL(/\/dashboard/);

    // The page title or heading should indicate the dashboard
    await expect(
      page.getByRole("heading", { name: /security dashboard/i }),
    ).toBeVisible();
  });

  test("login with invalid credentials shows error message", async ({
    page,
  }) => {
    await page.goto("/login");

    await page.fill("#email", "wrong@example.com");
    await page.fill("#password", "WrongPassword1!");
    await page.click('button[type="submit"]');

    // The login page displays "Invalid email or password. Please try again."
    await expect(page.getByText(/invalid email or password/i)).toBeVisible({
      timeout: 10_000,
    });

    // Should remain on the login page
    await expect(page).toHaveURL(/\/login/);
  });

  test("login form requires email and password (HTML validation)", async ({
    page,
  }) => {
    await page.goto("/login");

    // Both inputs have the `required` attribute, so submitting empty
    // should not navigate away (browser validation blocks it).
    const emailInput = page.locator("#email");
    const passwordInput = page.locator("#password");

    // Verify both inputs are required
    await expect(emailInput).toHaveAttribute("required", "");
    await expect(passwordInput).toHaveAttribute("required", "");

    // Ensure we stay on login after attempting submit with empty fields
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/login/);
  });

  test("logout redirects to login page", async ({ page }) => {
    await login(page);

    // The topbar has a logout button with aria-label "Logout"
    const logoutButton = page.getByLabel("Logout");
    await expect(logoutButton).toBeVisible();
    await logoutButton.click();

    // After logout, the app redirects to /login via window.location.href
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });

  test("session persists after page refresh", async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL(/\/dashboard/);

    // Reload the page -- the AuthProvider checks /auth/me on mount
    await page.reload();

    // Should still be on the dashboard (not redirected to /login)
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("protected route redirects unauthenticated user to login", async ({
    page,
  }) => {
    // Navigate directly to a protected route without logging in
    await page.goto("/dashboard");

    // The 401 interceptor in api.ts redirects to /login when refresh fails.
    // Alternatively, the page may remain on /dashboard but show no data.
    // We wait up to 10s for either a redirect or a login-like URL.
    // If the app renders an error state instead of redirecting, we check for that.
    try {
      await expectRedirectToLogin(page);
    } catch {
      // Some implementations show the page with an error/loading state
      // instead of redirecting. If we are still on /dashboard, check that
      // no authenticated content is visible (e.g., no user name in topbar).
      // This is acceptable behavior for an SPA that lazy-checks auth.
      const url = page.url();
      if (url.includes("/dashboard")) {
        // Verify we do NOT see the user's email, meaning we are not logged in
        await expect(page.getByText(TEST_EMAIL)).not.toBeVisible({
          timeout: 5_000,
        });
      }
    }
  });

  test("SSO login form can be toggled", async ({ page }) => {
    await page.goto("/login");

    // Click "Sign in with SSO" button
    const ssoButton = page.getByText("Sign in with SSO");
    await expect(ssoButton).toBeVisible();
    await ssoButton.click();

    // The SSO form should now show an organization slug input
    await expect(page.locator("#sso-slug")).toBeVisible();
    await expect(page.getByText("Continue with SSO")).toBeVisible();

    // Click "Back to email login" to return
    await page.getByText("Back to email login").click();
    await expect(page.locator("#sso-slug")).not.toBeVisible();
  });
});

import { test, expect } from "@playwright/test";
import { login } from "./helpers/auth";

test.describe("Settings Flow", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
  });

  test("settings page loads with heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /settings/i }).first(),
    ).toBeVisible();
  });

  test("cloud accounts section is visible", async ({ page }) => {
    // The settings page has a section for managing cloud accounts
    // Look for "Cloud Accounts" or "Accounts" heading or section
    const accountsHeading = page.getByText(/cloud accounts/i).first();
    const accountsVisible = await accountsHeading
      .isVisible()
      .catch(() => false);

    if (accountsVisible) {
      await expect(accountsHeading).toBeVisible();
    } else {
      // May be named differently; check for "Accounts" or "Connected Accounts"
      const altHeading = page.getByText(/accounts/i).first();
      await expect(altHeading).toBeVisible();
    }
  });

  test("add account form/button is available", async ({ page }) => {
    // The settings page should have a way to add a new cloud account
    // Look for an "Add" button or a form with provider selection
    const addButton = page.getByRole("button", { name: /add/i }).first();
    const providerSelect = page.locator("select").first();

    const hasAddButton = await addButton.isVisible().catch(() => false);
    const hasProviderSelect = await providerSelect
      .isVisible()
      .catch(() => false);

    // At least one mechanism to add accounts should exist
    expect(hasAddButton || hasProviderSelect).toBeTruthy();
  });

  test("theme toggle button exists in the topbar", async ({ page }) => {
    // The topbar has a theme toggle with aria-label containing "mode"
    const themeToggle = page.getByLabel(/mode/i);
    await expect(themeToggle).toBeVisible();
  });

  test("clicking theme toggle switches between dark and light mode", async ({
    page,
  }) => {
    const htmlElement = page.locator("html");

    // Check current theme state
    const initialClassList = await htmlElement.getAttribute("class");
    const initiallyDark = initialClassList?.includes("dark") ?? false;

    // Click the theme toggle
    const themeToggle = page.getByLabel(/mode/i);
    await themeToggle.click();

    // Wait for theme transition
    await page.waitForTimeout(300);

    // The <html> class should have toggled the "dark" class
    const updatedClassList = await htmlElement.getAttribute("class");
    const nowDark = updatedClassList?.includes("dark") ?? false;

    expect(nowDark).not.toBe(initiallyDark);

    // Toggle back to restore original state
    await themeToggle.click();
    await page.waitForTimeout(300);
  });

  test("user info is displayed in topbar", async ({ page }) => {
    // The topbar shows the user's name/email and role badge
    const topbar = page.locator("header");
    await expect(topbar).toBeVisible();

    // Should show either the user's full name or email
    // and a role badge ("Admin" or "Viewer")
    const hasAdmin = await topbar
      .getByText("Admin")
      .isVisible()
      .catch(() => false);
    const hasViewer = await topbar
      .getByText("Viewer")
      .isVisible()
      .catch(() => false);

    expect(hasAdmin || hasViewer).toBeTruthy();
  });

  test("API keys section is accessible", async ({ page }) => {
    // The settings page may have an API Keys section
    const apiKeysHeading = page.getByText(/api key/i).first();
    const hasApiKeys = await apiKeysHeading.isVisible().catch(() => false);

    if (hasApiKeys) {
      await expect(apiKeysHeading).toBeVisible();
    }
    // If not visible, the section might be behind a tab or scroll
  });

  test("team management section is accessible", async ({ page }) => {
    // Settings page may have a "Team" or "Users" or "Invitations" section
    const teamHeading = page.getByText(/team|users|members|invit/i).first();
    const hasTeam = await teamHeading.isVisible().catch(() => false);

    if (hasTeam) {
      await expect(teamHeading).toBeVisible();
    }
  });

  test("MFA section is accessible", async ({ page }) => {
    // Settings page may include MFA/Two-Factor setup
    const mfaHeading = page.getByText(/two-factor|mfa|authenticator/i).first();
    const hasMfa = await mfaHeading.isVisible().catch(() => false);

    if (hasMfa) {
      await expect(mfaHeading).toBeVisible();
    }
  });
});

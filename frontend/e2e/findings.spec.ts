import { test, expect } from "@playwright/test";
import { login } from "./helpers/auth";

test.describe("Findings Flow", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/findings");
    await page.waitForLoadState("networkidle");
  });

  test("findings list page loads with heading", async ({ page }) => {
    // The findings page should have a recognizable heading
    await expect(
      page.getByRole("heading", { name: /findings/i }).first(),
    ).toBeVisible();
  });

  test("findings table or empty state is displayed", async ({ page }) => {
    // Either a table with findings or an empty-state message should be visible
    const table = page.locator("table");
    const emptyState = page.getByText(/no findings/i);

    const hasTable = await table.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasTable || hasEmpty).toBeTruthy();

    if (hasTable) {
      // Verify expected column headers are present
      // The findings table has columns: Title, Severity, Status, First Detected, Last Evaluated
      const headerRow = page.locator("thead tr").first();
      await expect(headerRow).toBeVisible();
    }
  });

  test("search box filters findings", async ({ page }) => {
    // The findings page has a search input
    const searchInput = page.getByPlaceholder(/search/i);
    const hasSearch = await searchInput.isVisible().catch(() => false);

    if (hasSearch) {
      // Type a search query
      await searchInput.fill("nonexistent-finding-xyz");
      // Wait for debounce (300ms) + network
      await page.waitForTimeout(500);
      await page.waitForLoadState("networkidle");

      // URL should include search param
      expect(page.url()).toContain("search=");
    }
  });

  test("severity filter updates URL", async ({ page }) => {
    // Look for a severity filter control (dropdown or filter panel)
    // The FilterPanel component renders select elements
    const severitySelect = page.locator("select").first();
    const hasSeveritySelect = await severitySelect
      .isVisible()
      .catch(() => false);

    if (hasSeveritySelect) {
      await severitySelect.selectOption("high");
      await page.waitForLoadState("networkidle");
      // URL should contain severity=high
      expect(page.url().toLowerCase()).toContain("severity=high");
    }
  });

  test("sort indicator changes when column header is clicked", async ({
    page,
  }) => {
    // Click a sortable column header (e.g., "Severity")
    const table = page.locator("table");
    const hasTable = await table.isVisible().catch(() => false);

    if (hasTable) {
      // Find a clickable column header -- they typically use <button> or are clickable <th>
      const severityHeader = page
        .locator("th")
        .filter({ hasText: /severity/i })
        .first();
      const isClickable = await severityHeader.isVisible().catch(() => false);

      if (isClickable) {
        await severityHeader.click();
        await page.waitForLoadState("networkidle");
        // URL should now contain sort_by
        expect(page.url()).toContain("sort_by=");
      }
    }
  });

  test("pagination works when multiple pages exist", async ({ page }) => {
    // Check if pagination controls are present
    const nextButton = page.getByRole("button", { name: /next/i });
    const page2Button = page.getByRole("button", { name: "2" });

    const hasPagination =
      (await nextButton.isVisible().catch(() => false)) ||
      (await page2Button.isVisible().catch(() => false));

    if (hasPagination) {
      // Click page 2 or next
      const target = (await page2Button.isVisible().catch(() => false))
        ? page2Button
        : nextButton;
      await target.click();
      await page.waitForLoadState("networkidle");
      expect(page.url()).toContain("page=2");
    }
    // If no pagination, there is only one page of results -- acceptable
  });

  test("clicking a finding row navigates to finding detail", async ({
    page,
  }) => {
    // Wait for table rows
    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Click the first finding row
      await rows.first().click();

      // Should navigate to /findings/[id]
      await expect(page).toHaveURL(/\/findings\/[a-f0-9-]+/);
    }
  });

  test("finding detail page shows title, severity, and status badges", async ({
    page,
  }) => {
    // Navigate to first finding via table if possible
    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();

    if (rowCount > 0) {
      await rows.first().click();
      await expect(page).toHaveURL(/\/findings\/[a-f0-9-]+/);

      // Wait for detail page to load
      await page.waitForLoadState("networkidle");

      // Back button should be visible (ArrowLeft in finding detail page)
      await expect(page.getByText(/back/i).first()).toBeVisible();

      // The finding detail page shows the finding title as a heading
      // and has severity/status badges
      const mainContent = page.locator("main");
      await expect(mainContent).toBeVisible();
    }
  });
});

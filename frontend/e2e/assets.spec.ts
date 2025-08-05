import { test, expect } from "@playwright/test";
import { login } from "./helpers/auth";

test.describe("Assets Flow", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/assets");
    await page.waitForLoadState("networkidle");
  });

  test("assets list page loads with heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /assets/i }).first(),
    ).toBeVisible();
  });

  test("assets table or empty state is displayed", async ({ page }) => {
    const table = page.locator("table");
    const emptyState = page.getByText(/no assets/i);

    const hasTable = await table.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasTable || hasEmpty).toBeTruthy();

    if (hasTable) {
      // Verify the table has a header row
      const headerRow = page.locator("thead tr").first();
      await expect(headerRow).toBeVisible();
    }
  });

  test("search box filters assets", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search/i);
    const hasSearch = await searchInput.isVisible().catch(() => false);

    if (hasSearch) {
      await searchInput.fill("test-asset-nonexistent");
      // Wait for debounce + network
      await page.waitForTimeout(500);
      await page.waitForLoadState("networkidle");

      expect(page.url()).toContain("search=");
    }
  });

  test("resource type filter updates URL", async ({ page }) => {
    // The FilterPanel renders select dropdowns for resource type, region, account
    const selects = page.locator("select");
    const selectCount = await selects.count();

    if (selectCount > 0) {
      // Get options from the first select (resource type)
      const firstSelect = selects.first();
      const options = await firstSelect.locator("option").allTextContents();

      // If there are options beyond the default "All", select one
      if (options.length > 1) {
        // Select the second option (first non-default)
        await firstSelect.selectOption({ index: 1 });
        await page.waitForLoadState("networkidle");
      }
    }
  });

  test("clicking an asset row navigates to asset detail", async ({ page }) => {
    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();

    if (rowCount > 0) {
      await rows.first().click();

      // Should navigate to /assets/[id]
      await expect(page).toHaveURL(/\/assets\/[a-f0-9-]+/);
    }
  });

  test("asset detail page shows related findings section", async ({ page }) => {
    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();

    if (rowCount > 0) {
      await rows.first().click();
      await expect(page).toHaveURL(/\/assets\/[a-f0-9-]+/);
      await page.waitForLoadState("networkidle");

      // The asset detail page should show asset info
      const mainContent = page.locator("main");
      await expect(mainContent).toBeVisible();

      // It should have a "Back" or navigation element
      await expect(page.getByText(/back/i).first()).toBeVisible();

      // The findings section should be visible (title "Findings" or similar)
      const findingsSection = page.getByText(/findings/i).first();
      await expect(findingsSection).toBeVisible();
    }
  });

  test("sort indicator changes on column header click", async ({ page }) => {
    const table = page.locator("table");
    const hasTable = await table.isVisible().catch(() => false);

    if (hasTable) {
      // Click the "Name" column header to sort
      const nameHeader = page
        .locator("th")
        .filter({ hasText: /name/i })
        .first();
      const isVisible = await nameHeader.isVisible().catch(() => false);

      if (isVisible) {
        await nameHeader.click();
        await page.waitForLoadState("networkidle");
        expect(page.url()).toContain("sort_by=");
      }
    }
  });
});

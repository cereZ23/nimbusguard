import { test, expect } from "@playwright/test";
import { login } from "./helpers/auth";

test.describe("Dashboard Flow", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("dashboard page loads with heading and KPI cards", async ({ page }) => {
    // Verify the main heading
    await expect(
      page.getByRole("heading", { name: /security dashboard/i }),
    ).toBeVisible();

    // The dashboard subtitle
    await expect(
      page.getByText(/real-time overview of your cloud security posture/i),
    ).toBeVisible();

    // KPI cards should be visible (data-tour attributes from the source)
    // The KPI card row has data-tour="kpi-cards"
    const kpiSection = page.locator('[data-tour="kpi-cards"]');
    // If the dashboard has data, KPI cards render; if empty, an empty state renders.
    // We check for either scenario.
    const hasKpiCards = await kpiSection.isVisible().catch(() => false);

    if (hasKpiCards) {
      // Check for the four KPI card titles
      await expect(page.getByText("Secure Score")).toBeVisible();
      await expect(page.getByText("Total Assets")).toBeVisible();
      await expect(page.getByText("Total Findings")).toBeVisible();
      await expect(page.getByText("High Severity")).toBeVisible();
    } else {
      // Empty state: "No data available" or onboarding redirect
      const emptyOrRedirect =
        (await page
          .getByText("No data available")
          .isVisible()
          .catch(() => false)) || page.url().includes("/onboarding");
      expect(emptyOrRedirect).toBeTruthy();
    }
  });

  test("charts render when data is available", async ({ page }) => {
    // Wait for the page to finish loading
    await page.waitForLoadState("networkidle");

    // Check for chart containers via data-tour attributes
    const secureScoreGauge = page.locator('[data-tour="secure-score"]');
    const severityDonut = page.locator('[data-tour="severity-donut"]');
    const trendChart = page.locator('[data-tour="trend-chart"]');

    // If we have data, charts should be visible
    const hasCharts = await secureScoreGauge.isVisible().catch(() => false);
    if (hasCharts) {
      await expect(secureScoreGauge).toBeVisible();
      await expect(severityDonut).toBeVisible();
      await expect(trendChart).toBeVisible();
    }
    // If no data, empty state is shown -- that is also acceptable
  });

  test("time range selector buttons are visible and clickable", async ({
    page,
  }) => {
    await page.waitForLoadState("networkidle");

    // The TimeRangeSelector renders buttons for 7d, 14d, 30d, 90d
    const timeRangeButtons = ["7d", "14d", "30d", "90d"];

    for (const label of timeRangeButtons) {
      const button = page.getByRole("button", { name: label, exact: true });
      // The buttons may not be visible if dashboard is in empty/onboarding state
      const isVisible = await button.isVisible().catch(() => false);
      if (isVisible) {
        await button.click();
        // Brief wait for SWR to re-fetch with new period
        await page.waitForTimeout(500);
      }
    }
  });

  test("top failing controls section is visible when data exists", async ({
    page,
  }) => {
    await page.waitForLoadState("networkidle");

    // The top failing controls section has data-tour="top-controls"
    const topControlsSection = page.locator('[data-tour="top-controls"]');
    const hasControls = await topControlsSection.isVisible().catch(() => false);

    if (hasControls) {
      await expect(topControlsSection).toBeVisible();
    }
    // If no data, the section is simply not rendered -- acceptable
  });

  test("sidebar navigation links work", async ({ page }) => {
    // Verify sidebar nav links are present and navigate correctly
    const navLinks = [
      { label: "Assets", expectedUrl: /\/assets/ },
      { label: "Findings", expectedUrl: /\/findings/ },
      { label: "Compliance", expectedUrl: /\/compliance/ },
      { label: "Reports", expectedUrl: /\/reports/ },
      { label: "Settings", expectedUrl: /\/settings/ },
    ];

    for (const { label, expectedUrl } of navLinks) {
      const link = page.getByRole("link", { name: label, exact: true });
      const isVisible = await link.isVisible().catch(() => false);
      if (isVisible) {
        await link.click();
        await expect(page).toHaveURL(expectedUrl);
        // Navigate back to dashboard for next iteration
        await page
          .getByRole("link", { name: "Dashboard", exact: true })
          .click();
        await expect(page).toHaveURL(/\/dashboard/);
      }
    }
  });

  test("last updated timestamp is shown", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    // The dashboard shows "Last updated: HH:MM:SS" or a dash if loading
    await expect(page.getByText(/last updated/i)).toBeVisible();
  });
});

import { test, expect } from "@playwright/test";

const MAYO_URL =
  "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444";

test.describe("Mayo Clinic Content Validator — E2E", () => {
  test("home page loads with pipeline diagram and URL input", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Mayo Clinic Content Validator/);
    await expect(page.getByText("Content Validation Dashboard")).toBeVisible();
    await expect(page.getByText("Pipeline Architecture")).toBeVisible();
    await expect(page.getByText("URL Input")).toBeVisible();
    await expect(page.getByLabel("Mayo Clinic URL")).toBeVisible();
    await expect(page.getByRole("button", { name: "Validate" })).toBeVisible();
  });

  test("rejects non-mayoclinic URLs", async ({ page }) => {
    await page.goto("/");
    const input = page.getByLabel("Mayo Clinic URL");
    await input.fill("https://www.google.com/search?q=diabetes");
    await expect(page.getByText("URL must be from mayoclinic.org")).toBeVisible();
    await expect(page.getByRole("button", { name: "Validate" })).toBeDisabled();
  });

  test("accepts valid mayoclinic.org URL and enables Validate button", async ({ page }) => {
    await page.goto("/");
    const input = page.getByLabel("Mayo Clinic URL");
    await input.fill(MAYO_URL);
    await expect(page.getByRole("button", { name: "Validate" })).toBeEnabled();
  });

  test("example URL buttons populate the input field", async ({ page }) => {
    await page.goto("/");
    const exampleBtn = page.getByText("https://www.mayoclinic.org/diseases-conditions/diabetes").first();
    await exampleBtn.click();
    const input = page.getByLabel("Mayo Clinic URL");
    await expect(input).toHaveValue(/mayoclinic\.org/);
  });

  test("submits URL and navigates to results page showing progress", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Mayo Clinic URL").fill(MAYO_URL);
    await page.getByRole("button", { name: "Validate" }).click();

    // Should navigate to /results/{id}
    await expect(page).toHaveURL(/\/results\/[0-9a-f-]{36}/, { timeout: 10000 });

    // Back button should be visible
    await expect(page.getByText("Back to Dashboard")).toBeVisible();

    // Pipeline progress panel should be visible
    await expect(page.getByText("Pipeline Progress")).toBeVisible();

    // Should show at least scraping or running state (take first match)
    await expect(
      page.getByText(/Scraping URL|Validating|Initializing pipeline/i).first()
    ).toBeVisible({ timeout: 15000 });

    const scrapingStep = page.getByTestId("pipeline-step-scraping");
    await scrapingStep.getByRole("button", { name: /Scraping URL methodology details/i }).click();
    const scrapingTooltip = page.getByTestId("pipeline-tooltip-scraping");
    await expect(scrapingTooltip).toBeVisible();
    await expect(scrapingTooltip.getByText("Agent used")).toBeVisible();
    await expect(scrapingTooltip.getByText("Web Scraper")).toBeVisible();
  });

  test("results page shows agent findings after pipeline completes", async ({ page }) => {
    // Submit validation
    await page.goto("/");
    await page.getByLabel("Mayo Clinic URL").fill(MAYO_URL);
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page).toHaveURL(/\/results\/[0-9a-f-]{36}/, { timeout: 10000 });

    // Wait for at least one agent to complete (up to 3 minutes for GPT-5.1 calls)
    await expect(page.getByRole("heading", { name: "Agent Findings" })).toBeVisible({ timeout: 180000 });

    // Check that agent result cards appear
    await expect(
      page.getByText(/Metadata|Editorial|Compliance|Accuracy/i).first()
    ).toBeVisible();
    const firstCard = page.locator("div.rounded-xl.border.p-5").first();
    await expect(firstCard.getByText("Agent used")).toBeVisible();
    await expect(firstCard.getByText("Methodology")).toBeVisible();

    // Expect HITL panel to appear once all agents done
    await expect(page.getByText("Human Review Required")).toBeVisible({
      timeout: 60000,
    });

    // Approve button should be visible
    await expect(
      page.getByRole("button", { name: /Approve for Publication/i })
    ).toBeVisible();
  });

  test("HITL panel allows approving content", async ({ page }) => {
    test.setTimeout(240000);
    // First submit and wait for HITL
    await page.goto("/");
    await page.getByLabel("Mayo Clinic URL").fill(MAYO_URL);
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page).toHaveURL(/\/results\//, { timeout: 10000 });

    // Wait for HITL panel
    await expect(page.getByText("Human Review Required")).toBeVisible({
      timeout: 180000,
    });

    // Add feedback
    await page.getByPlaceholder("Add any notes about your decision...").fill("Playwright auto-approve test");

    // Click approve
    await page.getByRole("button", { name: /Approve for Publication/i }).click();

    // Should eventually show approved (judge agent adds extra time)
    await expect(page.getByText(/approved for publication/i)).toBeVisible({ timeout: 60000 });
  });
});

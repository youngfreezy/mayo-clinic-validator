#!/usr/bin/env node
/**
 * Playwright demo recorder — captures a full walkthrough of the app and saves
 * a video to ~/Desktop/mayo-validator-demo.webm
 *
 * Usage (from project root, while the app is running):
 *   node scripts/record-demo.js
 *
 * Requires: npx playwright install chromium  (run once if needed)
 */

const path = require("path");
const fs = require("fs");
const { chromium } = require(require.resolve("playwright", {
  paths: [path.join(__dirname, "..", "frontend", "node_modules")],
}));

const VIDEO_DIR = path.join(__dirname, "..", "..", "Desktop"); // ~/Desktop
const OUT_NAME  = "mayo-validator-demo.webm";
const MAYO_URL  =
  "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444";

async function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

(async () => {
  console.log("Launching browser…");

  // Use a large fixed viewport that fills the screen
  const W = 1800, H = 1024;

  const browser = await chromium.launch({
    headless: false,
    slowMo: 60,
    args: [
      `--window-size=${W},${H}`,
      "--window-position=0,0",
      "--start-fullscreen",
    ],
  });

  const ctx = await browser.newContext({
    viewport: { width: W, height: H },
    recordVideo: {
      dir: VIDEO_DIR,
      size: { width: W, height: H },
    },
  });

  const page = await ctx.newPage();

  try {
    // ── 1. Home page ────────────────────────────────────────────────────────
    console.log("Step 1: Home page");
    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
    await delay(3000);   // pause so viewers can read the dashboard

    // ── 2. Open architecture modal ──────────────────────────────────────────
    console.log("Step 2: Architecture modal");
    await page.getByTitle("View architecture diagram").click();
    await delay(4000);   // let modal fully animate in and viewers read it

    // scroll down inside the modal to show the RAG section
    const modal = page.locator(".overflow-y-auto").first();
    await modal.evaluate((el) => el.scrollBy({ top: 350, behavior: "smooth" }));
    await delay(3500);
    await modal.evaluate((el) => el.scrollBy({ top: -350, behavior: "smooth" }));
    await delay(2500);

    // click the explicit X close button (more visible than Escape)
    await page.locator("button[class*='hover:text-gray-600']").first().click();
    await delay(2000);   // wait for modal to fully close

    // ── 3. Fill URL and validate ────────────────────────────────────────────
    console.log("Step 3: Submit URL for validation");
    const input = page.getByLabel("Mayo Clinic URL");
    await input.click();
    await delay(500);
    await input.fill(MAYO_URL);
    await delay(2000);   // pause so URL is readable
    await page.getByRole("button", { name: "Validate" }).click();

    // ── 4. Results page — watch agents run ──────────────────────────────────
    console.log("Step 4: Waiting for results page…");
    await page.waitForURL(/\/results\/[0-9a-f-]{36}/, { timeout: 15000 });
    await delay(3000);   // show the initial pipeline progress state

    console.log("Step 5: Waiting for agents to complete (up to 3 min)…");
    await page.getByText("Human Review Required").waitFor({ timeout: 200000 });
    await delay(4000);   // let viewers read all 4 agent result cards

    // scroll down slowly so all agent cards are visible
    await page.evaluate(() => window.scrollBy({ top: 400, behavior: "smooth" }));
    await delay(2500);
    await page.evaluate(() => window.scrollBy({ top: -400, behavior: "smooth" }));
    await delay(2000);

    // ── 5. HITL — approve ───────────────────────────────────────────────────
    console.log("Step 6: Approving content");
    const feedback = page.getByPlaceholder("Add any notes about your decision...");
    await feedback.click();
    await delay(500);
    await feedback.fill("Looks good — approved for demo recording.");
    await delay(2000);   // pause so feedback text is readable
    await page.getByRole("button", { name: /Approve for Publication/i }).click();

    // wait for approved state
    await page.getByText(/approved for publication/i).waitFor({ timeout: 30000 });
    await delay(4000);   // linger on the success state

    // ── 6. Back to dashboard ─────────────────────────────────────────────────
    console.log("Step 7: Back to dashboard");
    await page.getByText("Back to Dashboard").click();
    await page.waitForURL("http://localhost:3000", { timeout: 10000 });
    await delay(3000);

    // scroll down to show the validation history table
    await page.evaluate(() => window.scrollTo({ top: 600, behavior: "smooth" }));
    await delay(4000);   // let viewers read the history table

    console.log("Recording complete — closing browser.");
  } catch (err) {
    console.error("Recording error:", err.message);
  } finally {
    // Must close context (not just browser) to flush the video file
    await ctx.close();
    await browser.close();

    // Playwright names the file with a random UUID — rename to our target name
    const files = fs.readdirSync(VIDEO_DIR)
      .filter((f) => f.endsWith(".webm"))
      .map((f) => ({ name: f, mtime: fs.statSync(path.join(VIDEO_DIR, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);

    if (files.length > 0) {
      const src = path.join(VIDEO_DIR, files[0].name);
      const dst = path.join(VIDEO_DIR, OUT_NAME);
      if (src !== dst) fs.renameSync(src, dst);
      console.log(`\nVideo saved to: ${dst}`);
    } else {
      console.log("No video file found in output dir.");
    }
  }
})();

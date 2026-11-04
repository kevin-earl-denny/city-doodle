import { test, expect } from "@playwright/test";

test.describe("Home Page", () => {
  test("has title", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("City Doodle")).toBeVisible();
  });

  test.describe("navigation", () => {
    // Without a Clerk key the app renders only the "sign-in is not configured" screen (CITY-644).
    test.skip(
      !process.env.VITE_CLERK_PUBLISHABLE_KEY,
      "Needs VITE_CLERK_PUBLISHABLE_KEY (Clerk keys: CITY-645)"
    );

    test("can navigate to about page", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("link", { name: /about/i }).click();
      await expect(page.getByText("About")).toBeVisible();
    });

    test("can navigate back to home", async ({ page }) => {
      await page.goto("/about");
      await page.getByRole("link", { name: /home/i }).click();
      await expect(page.getByText("City Doodle")).toBeVisible();
    });
  });
});

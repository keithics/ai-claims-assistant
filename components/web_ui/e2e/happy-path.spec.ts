import { expect, test, type Locator } from "@playwright/test";

const API = "http://localhost:18000";
const CLAIMS = "http://localhost:18001";

async function expectNotClipped(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThan(10);
  expect(
    await locator.evaluate((el) => el.scrollWidth > el.clientWidth + 1),
  ).toBe(false);
}

test.beforeEach(async ({ page }) => {
  await page.route("**/config.json", (route) =>
    route.fulfill({ json: { apiBaseUrl: API } }),
  );
});

test("check a claim, draft one, approve it and see the usage", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Country")).toContainText("Philippines");

  const box = page.getByLabel("Type your message");
  await box.fill("What is the status of claim PH-1042?");
  await box.press("Enter");
  await expect(page.getByText("Claim PH-1042 is under review.")).toBeVisible();

  const turn1 = page.getByRole("region", { name: "Turn 1" });
  await expect(turn1).toBeVisible();
  await expect(turn1.getByText("small-a")).toBeVisible();
  await expect(turn1).toContainText("Model calls");

  await box.fill(
    "I had a car accident on 2026-10-20, rear-ended at a junction, damage about 12000 PHP. Please file a claim.",
  );
  await box.press("Enter");
  await expect(
    page.getByText("Claims waiting for your approval: 1"),
  ).toBeVisible();

  await page.getByRole("link", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: "PH-5001" })).toBeVisible();
  await expect(
    page.getByText("Rear-ended at a junction", { exact: false }),
  ).toBeVisible();

  const before = await request.get(`${CLAIMS}/claims/PH-5001`);
  expect((await before.json()).status).toBe("draft");

  await page.getByRole("button", { name: "Approve and file" }).click();
  await expect(page.getByText("Claim PH-5001 was filed.")).toBeVisible();

  const after = await request.get(`${CLAIMS}/claims/PH-5001`);
  expect((await after.json()).status).toBe("submitted");

  await page.getByRole("link", { name: "Chat" }).click();
  await expect(page.getByRole("region", { name: "Turn 2" })).toBeVisible();
  const total = page.getByRole("region", { name: "Conversation total" });
  await expect(total).toBeVisible();
  await expect(total).toContainText("Cost");
});

test("Thai and Japanese render without clipping", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page.getByLabel("Country")).toContainText("Thailand");

  await page.getByLabel("Country").selectOption("th");
  const thaiBox = page.getByLabel("พิมพ์ข้อความของคุณ");
  await thaiBox.fill("ต้องแจ้งเหตุภายในกี่วัน");
  await thaiBox.press("Enter");
  const thaiAnswer = page.locator('.message.assistant [lang="th"].text');
  await expect(thaiAnswer).toContainText("15");
  await expectNotClipped(thaiAnswer);
  await page.screenshot({
    path: testInfo.outputPath("thai.png"),
    fullPage: true,
  });

  await page.getByLabel("ประเทศ").selectOption("jp");
  const japaneseBox = page.getByLabel("メッセージを入力");
  await japaneseBox.fill("事故の連絡は何日以内ですか");
  await japaneseBox.press("Enter");
  const japaneseAnswer = page.locator('.message.assistant [lang="ja"].text');
  await expect(japaneseAnswer).toContainText("60");
  await expectNotClipped(japaneseAnswer);
  await page.screenshot({
    path: testInfo.outputPath("japanese.png"),
    fullPage: true,
  });
});

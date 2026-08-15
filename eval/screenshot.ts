/** 截图各视图：菜谱库、卡片浏览、做菜、买菜 + 移动端视口。 */

import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = "eval/screenshots";
mkdirSync(OUT, { recursive: true });

const BASE = "http://127.0.0.1:8000";

async function main() {
  const browser = await chromium.launch();
  const desktop = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });

  // 1. 菜谱库（桌面）
  const page1 = await desktop.newPage();
  await page1.goto(BASE, { waitUntil: "networkidle" });
  await page1.waitForTimeout(800);
  await page1.screenshot({ path: `${OUT}/1-library-desktop.png` });

  // 2. 卡片浏览模式
  await page1.locator(".lib-card").first().click();
  await page1.waitForTimeout(800);
  await page1.screenshot({ path: `${OUT}/2-card-browse.png`, fullPage: true });

  // 3. 做菜模式（桌面）
  await page1.locator(".mode-tab[data-mode='cook']").click();
  await page1.waitForTimeout(500);
  await page1.screenshot({ path: `${OUT}/3-cook-desktop.png` });

  // 4. 买菜模式（桌面）
  await page1.locator(".mode-tab[data-mode='shop']").click();
  await page1.waitForTimeout(500);
  await page1.screenshot({ path: `${OUT}/4-shop-desktop.png`, fullPage: true });

  // 5. 菜谱库（手机）
  const page2 = await mobile.newPage();
  await page2.goto(BASE, { waitUntil: "networkidle" });
  await page2.waitForTimeout(800);
  await page2.screenshot({ path: `${OUT}/5-library-mobile.png` });

  // 6. 做菜模式（手机）
  await page2.locator(".lib-card").first().click();
  await page2.waitForTimeout(800);
  await page2.locator(".mode-tab[data-mode='cook']").click();
  await page2.waitForTimeout(500);
  await page2.screenshot({ path: `${OUT}/6-cook-mobile.png` });

  await browser.close();
  console.log("截图完成");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

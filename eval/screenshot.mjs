import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = "/home/chen/testai/video-dehydrator/eval/screenshots";
mkdirSync(OUT, { recursive: true });
const BASE = "http://127.0.0.1:8000";

const browser = await chromium.launch();
const desktop = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });

const page1 = await desktop.newPage();
await page1.goto(BASE, { waitUntil: "networkidle" });
await page1.waitForTimeout(800);
await page1.screenshot({ path: `${OUT}/1-library-desktop.png` });

await page1.locator(".lib-card").first().click();
await page1.waitForTimeout(800);
await page1.screenshot({ path: `${OUT}/2-card-browse.png`, fullPage: true });

await page1.locator(".mode-tab[data-mode='cook']").click();
await page1.waitForTimeout(500);
await page1.screenshot({ path: `${OUT}/3-cook-desktop.png` });

await page1.locator(".mode-tab[data-mode='shop']").click();
await page1.waitForTimeout(500);
await page1.screenshot({ path: `${OUT}/4-shop-desktop.png`, fullPage: true });

const page2 = await mobile.newPage();
await page2.goto(BASE, { waitUntil: "networkidle" });
await page2.waitForTimeout(800);
await page2.screenshot({ path: `${OUT}/5-library-mobile.png` });

await page2.locator(".lib-card").first().click();
await page2.waitForTimeout(800);
await page2.locator(".mode-tab[data-mode='cook']").click();
await page2.waitForTimeout(500);
await page2.screenshot({ path: `${OUT}/6-cook-mobile.png` });

await browser.close();
console.log("截图完成");

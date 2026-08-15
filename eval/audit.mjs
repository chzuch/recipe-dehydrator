/** 程序化 UI 审计：检查布局溢出、触控目标、移动端适配、控制台错误、可见性问题。 */

import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const issues = [];
const ok = [];

function report(okFlag: boolean, msg: string): void {
  if (okFlag) ok.push(msg);
  else issues.push(msg);
}

async function auditView(page, viewName): Promise<void> {
  // 1. 控制台错误
  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text().slice(0, 200));
  });

  // 2. 横向溢出检测
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth > doc.clientWidth + 2;
  });
  report(!overflow, `${viewName}: 无横向溢出`);
  if (overflow) {
    // 找出最宽的溢出元素
    const wide = await page.evaluate(() => {
      const els = [...document.querySelectorAll("*")] as HTMLElement[];
      const offenders = els
        .filter((el) => el.scrollWidth > el.parentElement!.clientWidth + 4)
        .map((el) => `${el.tagName}.${el.className?.toString().slice(0, 30)}`)
        .slice(0, 5);
      return offenders;
    });
    if (wide.length) issues.push(`  ⚠️ 溢出元素: ${wide.join(", ")}`);
  }

  // 3. 小触控目标检测（<44px 的按钮）
  const small = await page.evaluate(() => {
    const btns = [...document.querySelectorAll("button, .lib-card, .step-dot")] as HTMLElement[];
    return btns
      .filter((b) => {
        const r = b.getBoundingClientRect();
        return r.width < 40 || r.height < 40;
      })
      .map((b) => `${b.tagName}.${b.className?.toString().slice(0, 20)} ${Math.round(b.getBoundingClientRect().width)}x${Math.round(b.getBoundingClientRect().height)}`)
      .slice(0, 8);
  });
  report(small.length === 0, `${viewName}: 触控目标 ≥40px`);
  if (small.length) issues.push(`  ⚠️ 小触控目标: ${small.join(", ")}`);

  // 4. 元素重叠检测（相邻步骤/区块是否互相覆盖）
  const overlap = await page.evaluate(() => {
    const els = [...document.querySelectorAll(".step, .lib-card, .ing, .panel")] as HTMLElement[];
    let hits = 0;
    for (let i = 0; i < els.length && hits < 3; i++) {
      const a = els[i].getBoundingClientRect();
      for (let j = i + 1; j < els.length; j++) {
        const b = els[j].getBoundingClientRect();
        const inter = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
          Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
        if (inter > 20 && a.width > 50 && b.width > 50) hits++;
      }
    }
    return hits;
  });
  report(overlap === 0, `${viewName}: 无明显元素重叠`);

  if (errors.length) issues.push(`  ⚠️ 控制台错误: ${errors.join(" | ")}`);
}

async function main() {
  const browser = await chromium.launch();
  const desktop = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });

  // 桌面：菜谱库 + 浏览 + 做菜 + 买菜
  const p1 = await desktop.newPage();
  await p1.goto(BASE, { waitUntil: "networkidle" });
  await p1.waitForTimeout(600);
  await auditView(p1, "菜谱库(桌面)");

  await p1.locator(".lib-card").first().click();
  await p1.waitForTimeout(600);
  await auditView(p1, "卡片浏览(桌面)");

  await p1.locator(".mode-tab[data-mode='cook']").click();
  await p1.waitForTimeout(400);
  await auditView(p1, "做菜(桌面)");

  await p1.locator(".mode-tab[data-mode='shop']").click();
  await p1.waitForTimeout(400);
  await auditView(p1, "买菜(桌面)");

  // 手机：菜谱库 + 做菜
  const p2 = await mobile.newPage();
  await p2.goto(BASE, { waitUntil: "networkidle" });
  await p2.waitForTimeout(600);
  await auditView(p2, "菜谱库(手机)");

  await p2.locator(".lib-card").first().click();
  await p2.waitForTimeout(600);
  await auditView(p2, "卡片(手机)");

  await p2.locator(".mode-tab[data-mode='cook']").click();
  await p2.waitForTimeout(400);
  await auditView(p2, "做菜(手机)");

  await browser.close();

  console.log("\n========== 审计结果 ==========");
  console.log(`✅ 通过 ${ok.length} 项`);
  console.log(`❌ 问题 ${issues.length} 项`);
  for (const i of issues) console.log(" - " + i);
  console.log("\n通过项：");
  for (const o of ok) console.log("   ✓ " + o);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

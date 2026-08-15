/** 做菜模式：一步一屏、大字、手势翻页、进度条、屏幕常亮、步骤导航栏。 */

import { esc, fmt } from "./card";
import type { Recipe, Step } from "../types";

const $ = (s: string): HTMLElement | null => document.querySelector(s);

let steps: Step[] = [];
let currentIdx = 0;
let wakeLock: WakeLockSentinel | null = null;

function renderStep(): void {
  const step = steps[currentIdx];
  if (!step) return;
  const container = $("#cook-step");
  if (!container) return;
  const phase = step.phase || "烹饪";
  const img = step.frame_path
    ? `<img class="cook-img" src="/api/frames/${encodeURIComponent(step.frame_path)}" alt="步骤${step.index}">`
    : "";
  const gif = step.gif_path
    ? `<img class="cook-img" src="/api/frames/${encodeURIComponent(step.gif_path)}" alt="动作演示">`
    : "";
  container.innerHTML = `
    <div class="cook-phase">🔥 ${esc(phase)}</div>
    <div class="cook-title">${step.index}. ${esc(step.title)}</div>
    <div class="cook-media">${img}${gif}</div>
    <div class="cook-desc">${esc(step.description)}</div>
    ${step.done_when ? `<div class="cook-done">✅ ${esc(step.done_when)}</div>` : ""}
    ${step.tip ? `<div class="cook-tip">⚠️ ${esc(step.tip)}</div>` : ""}
  `;
  updateProgress();
  updateNav();
  renderStepBar();
}

function updateProgress(): void {
  const bar = $("#cook-progress") as HTMLElement | null;
  if (bar) bar.style.width = `${((currentIdx + 1) / steps.length) * 100}%`;
  const label = $("#cook-counter") as HTMLElement | null;
  if (label) label.textContent = `步骤 ${currentIdx + 1}/${steps.length}`;
}

function updateNav(): void {
  const prev = $("#cook-prev") as HTMLButtonElement | null;
  const next = $("#cook-next") as HTMLButtonElement | null;
  if (prev) prev.disabled = currentIdx === 0;
  if (next) next.disabled = currentIdx === steps.length - 1;
}

function renderStepBar(): void {
  const bar = $("#cook-stepbar");
  if (!bar) return;
  bar.innerHTML = steps
    .map(
      (s, i) =>
        `<button class="step-dot ${i === currentIdx ? "active" : ""}" data-i="${i}">${s.index}</button>`,
    )
    .join("");
  bar.querySelectorAll<HTMLElement>(".step-dot").forEach((el) => {
    el.addEventListener("click", () => {
      currentIdx = Number(el.dataset.i ?? 0);
      renderStep();
    });
  });
}

function goStep(delta: number): void {
  const next = currentIdx + delta;
  if (next < 0 || next >= steps.length) return;
  currentIdx = next;
  renderStep();
}

function renderIngredientsBar(recipe: Recipe): void {
  const bar = $("#cook-ingredients");
  if (!bar) return;
  const core = recipe.ingredients.filter((i) => i.category !== "调味料");
  bar.innerHTML = core
    .map((i) => `<span class="cook-ing">${esc(i.name)}</span>`)
    .join("");
}

async function requestWakeLock(): Promise<void> {
  try {
    // WakeLock 需要 https 或 localhost
    if ("wakeLock" in navigator && location.protocol === "http:" && location.hostname === "127.0.0.1") {
      wakeLock = await navigator.wakeLock.request("screen");
    }
  } catch {
    wakeLock = null;
  }
}

export function enterCookMode(recipe: Recipe, cardId: string): void {
  steps = recipe.steps;
  currentIdx = 0;
  ($("#cook-view") as HTMLElement | null)?.removeAttribute("hidden");
  renderIngredientsBar(recipe);
  renderStep();
  void requestWakeLock();
  // 详情页数据用于最后打卡（复用 cook API）
  window.dispatchEvent(new CustomEvent("cook-finish-ready", { detail: { cardId } }));
}

export function exitCookMode(): void {
  ($("#cook-view") as HTMLElement | null)?.setAttribute("hidden", "");
  if (wakeLock) {
    void wakeLock.release().catch(() => {});
    wakeLock = null;
  }
}

export function bindCookEvents(): void {
  $("#cook-prev")?.addEventListener("click", () => goStep(-1));
  $("#cook-next")?.addEventListener("click", () => goStep(1));
  document.addEventListener("keydown", (e) => {
    if (($("#cook-view") as HTMLElement | null)?.hidden) return;
    if (e.key === "ArrowLeft") goStep(-1);
    if (e.key === "ArrowRight") goStep(1);
  });
  // 触摸滑动翻页
  let touchX = 0;
  document.addEventListener("touchstart", (e) => {
    touchX = e.touches[0].clientX;
  });
  document.addEventListener("touchend", (e) => {
    if (($("#cook-view") as HTMLElement | null)?.hidden) return;
    const dx = e.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 60) goStep(dx < 0 ? 1 : -1);
  });
}

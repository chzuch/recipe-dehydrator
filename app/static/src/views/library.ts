/** 菜谱库视图（默认首页）：网格卡片、搜索、分类筛选、置顶、打卡。 */

import { api } from "../api";
import { esc } from "./card";
import { navigate } from "../router";
import type { CardEntry } from "../types";

const $ = (s: string): HTMLElement => document.querySelector(s) as HTMLElement;

let currentCards: CardEntry[] = [];

/** 主料分类：从卡片主料自动提取（去重、限前 6 个） */
function mainCategories(cards: CardEntry[]): string[] {
  const cats = new Set<string>();
  for (const { recipe } of cards) {
    for (const ing of recipe.ingredients) {
      if (ing.category === "主料") {
        cats.add(ing.name.replace(/(肉|鸡|排骨|鱼|虾|牛|羊|猪).*$/, (m) => m[0]));
      }
    }
  }
  return [...cats].slice(0, 6);
}

function coverOf(recipe: CardEntry["recipe"]): string {
  const last = recipe.steps[recipe.steps.length - 1];
  if (last?.frame_path) return `/api/frames/${encodeURIComponent(last.frame_path)}`;
  return "";
}

function renderGrid(cards: CardEntry[], category: string): string {
  const list = category === "全部" || !category ? cards : cards.filter(({ recipe }) =>
    recipe.ingredients.some((i) => i.category === "主料" && i.name.includes(category)),
  );
  if (list.length === 0) return '<div class="empty">还没有菜谱，去脱水一个吧</div>';
  return `<div class="lib-grid">${list
    .map(
      ({ id, recipe }) => `
    <div class="lib-card" data-card-id="${esc(id)}">
      <div class="lib-cover">${coverOf(recipe) ? `<img src="${esc(coverOf(recipe))}" alt="${esc(recipe.title)}">` : "🍲"}</div>
      <div class="lib-body">
        <div class="lib-title">${recipe.pinned ? "📌 " : ""}${esc(recipe.title)}</div>
        <div class="lib-meta">${esc(recipe.difficulty ?? "—")} · ${recipe.steps.length} 步</div>
        ${recipe.cooked_count > 0 ? `<div class="lib-cooked">🍳 做过 ${recipe.cooked_count} 次${recipe.last_cooked_at ? " · " + fmtDate(recipe.last_cooked_at) : ""}</div>` : ""}
      </div>
    </div>`,
    )
    .join("")}</div>`;
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export async function renderLibrary(): Promise<void> {
  const root = $("#library") as HTMLElement;
  root.hidden = false;
  ($("#card-view") as HTMLElement).hidden = true;

  const q = ($("#lib-search") as HTMLInputElement).value.trim();
  const category = ($("#lib-category") as HTMLSelectElement).value;
  const sort = ($("#lib-sort") as HTMLSelectElement).value;

  const cards = await api.cards({ q: q || undefined, category: category === "全部" ? undefined : category, sort });
  currentCards = cards ?? [];
  const cats = ["全部", ...mainCategories(currentCards)];
  const catOptions = cats
    .map((c) => `<option value="${esc(c)}" ${c === category ? "selected" : ""}>${esc(c)}</option>`)
    .join("");

  $("#lib-category").innerHTML = catOptions;
  const filtered = category === "全部" || !category ? currentCards : currentCards.filter(({ recipe }) =>
    recipe.ingredients.some((i) => i.category === "主料" && i.name.includes(category)),
  );
  $("#lib-grid").innerHTML = renderGrid(filtered, category);

  document.querySelectorAll<HTMLElement>(".lib-card").forEach((el) => {
    el.addEventListener("click", () => navigate({ name: "card", id: el.dataset.cardId ?? "" }));
  });
}

export function bindLibraryEvents(): void {
  $("#lib-search").addEventListener("input", () => void renderLibrary());
  $("#lib-category").addEventListener("change", () => void renderLibrary());
  $("#lib-sort").addEventListener("change", () => void renderLibrary());
}

/** 买菜模式：全屏清单、大勾选框、勾选划线沉底、调味料折叠。 */

import { esc } from "./card";
import { getHaveSet, toggleHave } from "../state";
import type { Ingredient, Recipe } from "../types";

const $ = (s: string): HTMLElement | null => document.querySelector(s);

const CATEGORIES = ["主料", "配料", "香料", "需提前自制"];
const CAT_ICON: Record<string, string> = {
  主料: "🥩",
  配料: "🧄",
  香料: "🌿",
  调味料: "🧂",
  需提前自制: "⚙️",
};

function groupByCategory(ingredients: Ingredient[]): Map<string, Ingredient[]> {
  const groups = new Map<string, Ingredient[]>();
  for (const ing of ingredients) {
    if (!groups.has(ing.category)) groups.set(ing.category, []);
    groups.get(ing.category)!.push(ing);
  }
  return groups;
}

export function enterShopMode(recipe: Recipe): void {
  const root = $("#shop-view");
  if (!root) return;
  root.removeAttribute("hidden");
  const groups = groupByCategory(recipe.ingredients);
  const have = getHaveSet();

  // 调味料单独折叠（家庭常备）
  const condiments = (groups.get("调味料") ?? []).map(shopItem).join("") || '<div class="empty">无</div>';
  const shoppingCats = CATEGORIES.filter((c) => groups.has(c));
  const main = shoppingCats
    .map((cat) => {
      const items = (groups.get(cat) ?? [])
        .map(shopItem)
        .join("");
      return `<div class="shop-cat"><div class="cat-label">${CAT_ICON[cat] ?? ""} ${esc(cat)}</div>${items}</div>`;
    })
    .join("");

  const total = recipe.ingredients.filter((ing) => ing.category !== "调味料").length;
  const checked = recipe.ingredients.filter((ing) => ing.category !== "调味料" && have.has(ing.name)).length;
  root.innerHTML = `
    <div class="shop-header"><div><span class="eyebrow">SHOPPING LIST</span><div class="shop-title">买菜清单</div></div><span id="shop-remaining" class="shop-remaining">还差 ${total - checked} 样</span></div>
    ${main}
    <details class="opt-group"><summary>调味料（家里常备）${(groups.get("调味料") ?? []).length} 项</summary>${condiments}</details>
    <div class="shop-done" id="shop-done-label">${have.size > 0 ? `已勾选 ${have.size} 项` : ""}</div>
  `;

  root.querySelectorAll<HTMLInputElement>(".shop-cb").forEach((cb) => {
    cb.addEventListener("change", () => {
      const name = cb.dataset.name ?? "";
      toggleHave(name, cb.checked);
      cb.closest(".shop-item")?.classList.toggle("done", cb.checked);
      const done = $("#shop-done-label");
      if (done) done.textContent = `已勾选 ${getHaveSet().size} 项`;
      const remaining = root.querySelector("#shop-remaining");
      if (remaining) remaining.textContent = `还差 ${root.querySelectorAll(".shop-cb:not(:checked)").length} 样`;
    });
  });
}

function shopItem(ing: Ingredient): string {
  const have = getHaveSet();
  const checked = have.has(ing.name);
  return `<div class="shop-item ${checked ? "done" : ""}">
    <input type="checkbox" class="shop-cb" data-name="${esc(ing.name)}" ${checked ? "checked" : ""}>
    <span>${esc(ing.name)}</span>
    <span class="amount">${esc(ing.amount || "")}</span>
  </div>`;
}

export function exitShopMode(): void {
  ($("#shop-view") as HTMLElement | null)?.setAttribute("hidden", "");
}

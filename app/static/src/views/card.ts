/** 卡片详情视图（浏览模式）：食材分组、步骤阶段分组、买菜清单、编辑。 */

import { api } from "../api";
import { getCurrentCard, getHaveSet, setCurrentCard, toggleHave } from "../state";
import type { Ingredient, Recipe, Step } from "../types";

const CATEGORIES = ["主料", "配料", "调味料", "香料", "需提前自制"];
// 买菜清单只包含需要购买的分类（调味料=家庭常备，不进清单）
const SHOPPING_CATEGORIES = ["主料", "配料", "香料", "需提前自制"];

const $ = (s: string): HTMLElement => document.querySelector(s) as HTMLElement;

export const esc = (s: unknown): string =>
  String(s ?? "").replace(/[&<>"']/g, (c) => `&${{ "&": "amp", "<": "lt", ">": "gt", '"': "quot", "'": "#39" }[c]};`);

export const fmt = (sec: number): string => {
  const s = Math.round(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

interface IngGroup {
  core: Ingredient[];
  opt: Ingredient[];
}

/** 按分类分组食材，组内核心在前、可选在后 */
function groupIngredients(ingredients: Ingredient[]): Array<[string, IngGroup]> {
  const groups = new Map<string, IngGroup>();
  for (const ing of ingredients || []) {
    const cat = ing.category || "调味料";
    if (!groups.has(cat)) groups.set(cat, { core: [], opt: [] });
    (ing.essential === false ? groups.get(cat)!.opt : groups.get(cat)!.core).push(ing);
  }
  const ordered: Array<[string, IngGroup]> = [];
  for (const cat of CATEGORIES) if (groups.has(cat)) ordered.push([cat, groups.get(cat)!]);
  for (const [cat, g] of groups) if (!CATEGORIES.includes(cat as never)) ordered.push([cat, g]);
  return ordered;
}

/** 按阶段分组步骤 */
function groupStepsByPhase(steps: Step[]): Array<[string, Step[]]> {
  const groups = new Map<string, Step[]>();
  for (const s of steps || []) {
    const p = s.phase || "烹饪";
    if (!groups.has(p)) groups.set(p, []);
    groups.get(p)!.push(s);
  }
  return [...groups.entries()];
}

function renderIngredient(ing: Ingredient, checkbox: boolean): string {
  const optional = ing.essential === false;
  const cb = checkbox
    ? `<input type="checkbox" data-ing="${esc(ing.name)}" class="have-cb">`
    : "";
  return `<div class="ing${optional ? " optional" : ""}">${cb}
    <span>${esc(ing.name)}</span>${ing.note ? `<span class="badge">${esc(ing.note)}</span>` : ""}
    <span class="amount">${esc(ing.amount || "")}</span></div>`;
}

export function renderCard(recipe: Recipe, cardId: string): void {
  setCurrentCard({ id: cardId, recipe });
  const hint = $("#empty-hint");
  if (hint) (hint as HTMLElement).hidden = true;
  ($("#card") as HTMLElement).hidden = false;
  const groups = groupIngredients(recipe.ingredients);
  $("#card").innerHTML = `
    <div class="recipe-title">${esc(recipe.title)}</div>
    <div class="meta">
      ${recipe.difficulty ? `<span>难度：${esc(recipe.difficulty)}</span>` : ""}
      ${recipe.servings ? `<span>份量：${esc(recipe.servings)}</span>` : ""}
      ${recipe.total_time ? `<span>耗时：${esc(recipe.total_time)}</span>` : ""}
      ${recipe.uploader ? `<span>UP：${esc(recipe.uploader)}</span>` : ""}
      ${recipe.cooked_count > 0 ? `<span>🍳 做过 ${recipe.cooked_count} 次</span>` : ""}
      ${recipe.source_url ? `<button class="btn-play" data-sec="0">▶ 播放原视频</button>` : ""}
    </div>
    <div id="player-wrap" hidden>
      <div class="player-bar">
        <span class="player-title">▶ 原视频片段</span>
        <button id="player-close" class="player-close" title="关闭播放器">✕ 收起</button>
      </div>
      <div class="player-frame">
        <iframe id="bili-player" frameborder="0" scrolling="no" allowfullscreen="true" title="原视频"></iframe>
      </div>
    </div>
    ${(recipe.warnings || []).slice(0, 1).map((w) => `<div class="warn">⚠️ ${esc(w)}</div>`).join("")}
    <div class="cols">
      <div>
        <h3>🥬 食材</h3>
        ${groups
          .map(([cat, g]) => {
            if (cat === "调味料") {
              const all = [...g.core, ...g.opt];
              return `<div class="cat"><div class="cat-label">调味料（家常常备）</div>
                <details class="opt-group"><summary>另需 ${all.length} 项家常调料，点开查看</summary>
                ${all.map((i) => renderIngredient(i, false)).join("")}</details></div>`;
            }
            return `<div class="cat">
              <div class="cat-label">${esc(cat)}</div>
              ${g.core.map((i) => renderIngredient(i, true)).join("")}
              ${g.opt.length ? `<details class="opt-group"><summary>可选 ${g.opt.length} 项（可省略）</summary>${g.opt.map((i) => renderIngredient(i, true)).join("")}</details>` : ""}
            </div>`;
          })
          .join("") || '<div class="empty">无食材</div>'}
      </div>
      <div>
        <h3>🔪 工具</h3>
        <div>${(recipe.tools || []).map((t) => `<span class="tool">${esc(t)}</span>`).join("") || '<div class="empty">未提及</div>'}</div>
        <h3 style="margin-top:16px">💡 小贴士</h3>
        <ul style="margin:0;padding-left:20px;font-size:14px">${(recipe.tips || []).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
      </div>
    </div>
    <h3 style="margin-top:18px">📋 步骤</h3>
    ${groupStepsByPhase(recipe.steps)
      .map(
        ([phase, phaseSteps]) => `
      <div class="phase-label">${esc(phase)}</div>
      ${phaseSteps
        .map(
          (s) => `
      <div class="step">
        <div class="no">${s.index}</div>
        <div class="body">
          <div><span class="title">${esc(s.title)}</span><span class="time">${fmt(s.start_sec)}–${fmt(s.end_sec)}</span></div>
          <div style="font-size:14px;margin-top:4px">${esc(s.description)}</div>
          ${s.done_when ? `<div class="done">✅ ${esc(s.done_when)}</div>` : ""}
          ${s.tip ? `<div class="tip">⚠️ ${esc(s.tip)}</div>` : ""}
          ${s.frame_path ? `<img src="/api/frames/${encodeURIComponent(s.frame_path)}" alt="步骤${s.index}">` : ""}
          ${s.gif_path ? `<img class="gif" src="/api/frames/${encodeURIComponent(s.gif_path)}" alt="步骤${s.index}动作演示">` : ""}
          ${recipe.source_url ? `<button class="watch btn-play" data-sec="${Math.round(s.start_sec)}">▶ 页内播放 ${fmt(s.start_sec)}</button>` : ""}
        </div>
      </div>`,
        )
        .join("")}`,
      )
      .join("") || '<div class="empty">无步骤</div>'}
    <div class="row-actions">
      <button id="btn-cook">🍳 今天做了</button>
      <button id="btn-pin">${recipe.pinned ? "📌 取消置顶" : "📌 置顶"}</button>
      <button id="btn-edit">✏️ 编辑</button>
      <button id="btn-delete" style="color:#c0392b">🗑 删除</button>
    </div>`;
  bindCardActions();
  renderShopping(recipe);
}

function bindCardActions(): void {
  document.querySelectorAll<HTMLInputElement>(".have-cb").forEach((cb) => {
    cb.addEventListener("change", () => {
      cb.closest(".ing")!.classList.toggle("done", cb.checked);
      toggleHave(cb.dataset.ing ?? "", cb.checked);
      const card = getCurrentCard();
      if (card) renderShopping(card.recipe);
    });
  });
  $("#btn-cook")?.addEventListener("click", cookCard);
  $("#btn-pin")?.addEventListener("click", pinCard);
  $("#btn-edit")?.addEventListener("click", editMode);
  $("#btn-delete")?.addEventListener("click", deleteCard);
  $("#player-close")?.addEventListener("click", () => {
    const wrap = $("#player-wrap") as HTMLElement;
    wrap.hidden = true;
    const iframe = $("#bili-player") as HTMLIFrameElement;
    iframe.src = "";
  });
  document.querySelectorAll<HTMLElement>(".btn-play").forEach((btn) => {
    btn.addEventListener("click", () => {
      const card = getCurrentCard();
      if (!card?.recipe.source_url) return;
      const sec = Number(btn.dataset.sec ?? 0);
      const bvid = extractBvid(card.recipe.source_url);
      if (!bvid) {
        // 无法解析 BV 号时也留在页内，提示而非跳转外链
        alert("无法从链接解析视频编号，无法在页内播放");
        return;
      }
      const iframe = $("#bili-player") as HTMLIFrameElement;
      iframe.src = `https://player.bilibili.com/player.html?bvid=${bvid}&page=1&t=${sec}&autoplay=1&high_quality=1`;
      ($("#player-wrap") as HTMLElement).hidden = false;
      ($("#player-wrap") as HTMLElement).scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

/** 从 B站链接任意位置提取 BV 号（兼容带参数/裸 BV 号） */
function extractBvid(url: string): string | null {
  const m = url.match(/BV[0-9A-Za-z]{8,}/);
  return m ? m[0] : null;
}

async function cookCard(): Promise<void> {
  const card = getCurrentCard();
  if (!card) return;
  try {
    const data = await api.cookCard(card.id);
    if (data) renderCard(data.recipe, data.id);
  } catch (e) {
    alert("打卡失败：" + (e as Error).message);
  }
}

async function pinCard(): Promise<void> {
  const card = getCurrentCard();
  if (!card) return;
  try {
    const data = await api.pinCard(card.id);
    if (data) renderCard(data.recipe, data.id);
  } catch (e) {
    alert("置顶失败：" + (e as Error).message);
  }
}

/** 买菜清单：只含「需要购买」的分类，核心优先，已勾选的「家中已有」不显示 */
function renderShopping(recipe: Recipe): void {
  const have = getHaveSet();
  const groups = groupIngredients(recipe.ingredients).filter(([cat]) =>
    SHOPPING_CATEGORIES.includes(cat as never),
  );
  const html = groups
    .map(([cat, g]) => {
      const core = g.core.filter((i) => !have.has(i.name));
      const items = core
        .map((i) => `<div class="ing"><span>${esc(i.name)}</span><span class="amount">${esc(i.amount || "")}</span></div>`)
        .join("");
      const opt = g.opt.length
        ? `<details class="opt-group"><summary>可选 ${g.opt.length} 项</summary>${g.opt
            .map((i) => `<div class="ing optional"><span>${esc(i.name)}</span><span class="amount">${esc(i.amount || "")}</span></div>`)
            .join("")}</details>`
        : "";
      if (!items && !opt) return "";
      return `<div class="cat"><div class="cat-label">${esc(cat)}</div>${items}${opt}</div>`;
    })
    .join("");
  $("#shopping").innerHTML = html || '<div class="empty" style="padding:10px">食材齐了 🎉</div>';
}

function editMode(): void {
  const card = getCurrentCard();
  if (!card) return;
  $("#card").innerHTML = `
    <h3>编辑菜谱 JSON（保存前请确认步骤顺序与时间区间）</h3>
    <textarea id="editor">${esc(JSON.stringify(card.recipe, null, 2))}</textarea>
    <div class="row-actions">
      <button class="primary" id="btn-save-edit">💾 保存</button>
      <button id="btn-cancel-edit">取消</button>
    </div>`;
  $("#card").classList.add("editing");
  $("#btn-save-edit").addEventListener("click", saveEdit);
  $("#btn-cancel-edit").addEventListener("click", () => location.reload());
}

async function saveEdit(): Promise<void> {
  const card = getCurrentCard();
  if (!card) return;
  try {
    const parsed = JSON.parse(($("#editor") as HTMLTextAreaElement).value) as Recipe;
    const data = await api.updateCard(card.id, parsed);
    if (data) renderCard(data.recipe, data.id);
    window.dispatchEvent(new CustomEvent("card-updated"));
  } catch (e) {
    alert("保存失败：" + (e as Error).message);
  }
}

async function deleteCard(): Promise<void> {
  const card = getCurrentCard();
  if (!card || !confirm("删除这张卡片？")) return;
  await api.deleteCard(card.id);
  location.reload();
}

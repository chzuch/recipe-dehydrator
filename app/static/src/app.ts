/** 应用入口：事件绑定、脱水触发、历史列表。 */

import { api } from "./api";
import { esc, renderCard } from "./views/card";

const $ = (s: string): HTMLElement => document.querySelector(s) as HTMLElement;

function setStatus(t: string): void {
  $("#status").textContent = t;
}

async function go(): Promise<void> {
  const url = ($("#url") as HTMLInputElement).value.trim();
  if (!url) {
    alert("请先粘贴视频链接");
    return;
  }
  const btn = $("#btn-go") as HTMLButtonElement;
  btn.disabled = true;
  btn.textContent = "脱水进行中…";
  setStatus("抓取字幕并切分中（通常 20–90 秒）…");
  try {
    const withGif = ($("#with-gif") as HTMLInputElement).checked;
    const data = await api.dehydrate(url, true, withGif);
    if (data) renderCard(data.recipe, data.card_id);
    await loadHistory();
    setStatus("✅ 完成");
  } catch (e) {
    setStatus("❌ " + (e as Error).message);
  } finally {
    btn.disabled = false;
    btn.textContent = "脱水";
  }
}

async function loadHistory(): Promise<void> {
  try {
    const list = await api.cards();
    $("#history").innerHTML = list?.length
      ? list
          .map(
            ({ id, recipe }) => `
      <div class="history-item" data-card-id="${esc(id)}">
        <div>${esc(recipe.title)}</div>
        <div class="sub">${(recipe.steps || []).length} 步 · ${esc(recipe.uploader || "")}</div>
      </div>`,
          )
          .join("")
      : '<div class="empty">还没有卡片</div>';
    document.querySelectorAll<HTMLElement>(".history-item").forEach((el) => {
      el.addEventListener("click", () => void openCard(el.dataset.cardId ?? ""));
    });
  } catch {
    /* 历史加载失败不阻断页面 */
  }
}

async function openCard(id: string): Promise<void> {
  try {
    const data = await api.getCard(id);
    if (data) renderCard(data.recipe, data.id);
  } catch (e) {
    alert((e as Error).message);
  }
}

function main(): void {
  $("#btn-go").addEventListener("click", () => void go());
  $("#url").addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") void go();
  });
  window.addEventListener("card-updated", () => void loadHistory());
  void loadHistory();
}

main();

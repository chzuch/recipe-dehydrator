/** 应用入口：路由分发、脱水触发。 */

import { api } from "./api";
import { navigate, onRouteChange } from "./router";
import { renderCard } from "./views/card";
import { bindLibraryEvents, renderLibrary } from "./views/library";

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
    if (data) {
      navigate({ name: "card", id: data.card_id });
      setStatus("✅ 完成");
    }
  } catch (e) {
    setStatus("❌ " + (e as Error).message);
  } finally {
    btn.disabled = false;
    btn.textContent = "脱水";
  }
}

async function showCard(id: string): Promise<void> {
  ($("#library") as HTMLElement).hidden = true;
  ($("#card-view") as HTMLElement).hidden = false;
  const data = await api.getCard(id);
  if (data) renderCard(data.recipe, data.id);
  else setStatus("❌ 卡片不存在");
}

async function showLibrary(): Promise<void> {
  await renderLibrary();
}

function main(): void {
  $("#btn-go").addEventListener("click", () => void go());
  $("#url").addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") void go();
  });
  $("#back-to-library").addEventListener("click", () => navigate({ name: "library" }));
  bindLibraryEvents();
  onRouteChange((route) => {
    if (route.name === "card") void showCard(route.id);
    else void showLibrary();
  });
}

main();

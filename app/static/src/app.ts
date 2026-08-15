/** 应用入口：路由分发、脱水触发、模式切换。 */

import { api } from "./api";
import { navigate, onRouteChange } from "./router";
import { getCurrentCard } from "./state";
import { renderCard } from "./views/card";
import { bindCookEvents, enterCookMode, exitCookMode } from "./views/cook";
import { bindLibraryEvents, renderLibrary } from "./views/library";
import { enterShopMode, exitShopMode } from "./views/shop";

const $ = (s: string): HTMLElement => document.querySelector(s) as HTMLElement;

let currentCardId = "";
let currentMode = "browse";

function setStatus(t: string): void {
  $("#status").textContent = t;
}

function switchMode(mode: string): void {
  if (mode === currentMode) return;
  currentMode = mode;
  document.querySelectorAll<HTMLElement>(".mode-tab").forEach((el) => {
    el.classList.toggle("active", el.dataset.mode === mode);
  });
  ($("#browse-view") as HTMLElement).hidden = mode !== "browse";
  ($("#cook-view") as HTMLElement).hidden = mode !== "cook";
  ($("#shop-view") as HTMLElement).hidden = mode !== "shop";
  if (mode !== "cook") exitCookMode();
  if (mode !== "shop") exitShopMode();
  const card = getCurrentCard();
  if (mode === "cook" && card) enterCookMode(card.recipe, card.id);
  if (mode === "shop" && card) enterShopMode(card.recipe);
}

function bindModeTabs(): void {
  document.querySelectorAll<HTMLElement>(".mode-tab").forEach((el) => {
    el.addEventListener("click", () => switchMode(el.dataset.mode ?? "browse"));
  });
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
  currentCardId = id;
  currentMode = "browse";
  document.querySelectorAll<HTMLElement>(".mode-tab").forEach((el) => {
    el.classList.toggle("active", el.dataset.mode === "browse");
  });
  ($("#library") as HTMLElement).hidden = true;
  ($("#card-view") as HTMLElement).hidden = false;
  ($("#browse-view") as HTMLElement).hidden = false;
  ($("#cook-view") as HTMLElement).hidden = true;
  ($("#shop-view") as HTMLElement).hidden = true;
  exitCookMode();
  exitShopMode();
  const data = await api.getCard(id);
  if (data) renderCard(data.recipe, data.id);
  else setStatus("❌ 卡片不存在");
}

async function showLibrary(): Promise<void> {
  ($("#card-view") as HTMLElement).hidden = true;
  exitCookMode();
  exitShopMode();
  await renderLibrary();
}

function main(): void {
  $("#btn-go").addEventListener("click", () => void go());
  $("#url").addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") void go();
  });
  $("#back-to-library").addEventListener("click", () => navigate({ name: "library" }));
  bindModeTabs();
  bindCookEvents();
  bindLibraryEvents();
  onRouteChange((route) => {
    if (route.name === "card") void showCard(route.id);
    else void showLibrary();
  });
}

// 引入避免未使用告警
void currentCardId;
main();


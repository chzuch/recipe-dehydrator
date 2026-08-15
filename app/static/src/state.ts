/** 前端状态：当前卡片 + 「家中已有」勾选集。 */

import type { Recipe } from "./types";

export interface CurrentCard {
  id: string;
  recipe: Recipe;
}

let currentCard: CurrentCard | null = null;
let haveSet = new Set<string>();

export function setCurrentCard(card: CurrentCard | null): void {
  currentCard = card;
  haveSet = new Set(); // 切卡片时重置勾选
}

export function getCurrentCard(): CurrentCard | null {
  return currentCard;
}

export function toggleHave(name: string, have: boolean): void {
  if (have) haveSet.add(name);
  else haveSet.delete(name);
}

export function getHaveSet(): ReadonlySet<string> {
  return haveSet;
}

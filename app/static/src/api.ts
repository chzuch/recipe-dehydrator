/** 后端 API 封装：所有 fetch 调用集中在此。 */

import type { CardEntry, DehydrateResult, Recipe } from "./types";

async function handle<T>(respPromise: Promise<Response>): Promise<T | null> {
  const resp = await respPromise;
  if (resp.status === 204) return null;
  const data: unknown = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = (data as { detail?: string }).detail ?? `请求失败 (${resp.status})`;
    throw new Error(detail);
  }
  return data as T;
}

export interface CardQuery {
  q?: string;
  category?: string;
  sort?: string;
}

export const api = {
  dehydrate(url: string, withFrames: boolean, withGif: boolean | null): Promise<DehydrateResult | null> {
    return handle(
      fetch("/api/dehydrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, with_frames: withFrames, with_gif: withGif }),
      }),
    );
  },

  cards(query: CardQuery = {}): Promise<CardEntry[] | null> {
    const sp = new URLSearchParams();
    if (query.q) sp.set("q", query.q);
    if (query.category) sp.set("category", query.category);
    if (query.sort) sp.set("sort", query.sort);
    const qs = sp.toString();
    return handle(fetch(`/api/cards${qs ? `?${qs}` : ""}`));
  },

  getCard(id: string): Promise<CardEntry | null> {
    return handle(fetch(`/api/cards/${id}`));
  },

  updateCard(id: string, recipe: Recipe): Promise<CardEntry | null> {
    return handle(
      fetch(`/api/cards/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(recipe),
      }),
    );
  },

  cookCard(id: string): Promise<CardEntry | null> {
    return handle(fetch(`/api/cards/${id}/cook`, { method: "POST" }));
  },

  pinCard(id: string): Promise<CardEntry | null> {
    return handle(fetch(`/api/cards/${id}/pin`, { method: "POST" }));
  },

  deleteCard(id: string): Promise<null> {
    return handle(fetch(`/api/cards/${id}`, { method: "DELETE" }));
  },
};

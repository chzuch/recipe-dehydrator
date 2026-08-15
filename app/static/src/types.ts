/**
 * 与后端 Pydantic schema 对齐的类型定义（app/domain/models.py）。
 * 后端 schema 变更时必须同步本文件（tsc --noEmit 会拦住不匹配）。
 */

export type IngredientCategory = "主料" | "配料" | "调味料" | "香料" | "需提前自制";

export interface Ingredient {
  name: string;
  amount: string | null;
  note: string | null;
  category: IngredientCategory;
  essential: boolean;
}

export interface Step {
  index: number;
  title: string;
  phase: string;
  description: string;
  done_when: string | null;
  tip: string | null;
  start_sec: number;
  end_sec: number;
  frame_path: string | null;
  gif_path: string | null;
}

export interface Recipe {
  title: string;
  source_url: string | null;
  source_title: string | null;
  uploader: string | null;
  difficulty: "简单" | "中等" | "困难" | null;
  servings: string | null;
  total_time: string | null;
  ingredients: Ingredient[];
  tools: string[];
  steps: Step[];
  tips: string[];
  warnings: string[];
  pinned: boolean;
  cooked_count: number;
  last_cooked_at: string | null;
}

export interface CardEntry {
  id: string;
  recipe: Recipe;
}

export interface DehydrateResult {
  card_id: string;
  recipe: Recipe;
}

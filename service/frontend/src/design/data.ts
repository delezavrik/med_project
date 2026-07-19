// Доменные данные и моки под дашборд. Структура повторяет контракт /dashboard
// (metrics / series / table / reviews / warnings / trace_steps) — заменить на fetch тривиально.

export type ClassKey =
  | "pos" | "size" | "quality" | "pack" | "card" | "price" | "return" | "delivery" | "other";

export interface ClassDef {
  key: ClassKey;
  name: string;
  short: string;
  cvar: string;
  share: number;
  delta: number;
  problem: boolean;
}

export const TOTAL = 48320;

export const CLASSES: ClassDef[] = [
  { key: "pos",      name: "Положительный / нейтральный отзыв",      short: "Позитив / нейтрал",       cvar: "--c-pos",      share: 0.581, delta: 2,  problem: false },
  { key: "size",     name: "Проблема с размером / посадкой",         short: "Размер / посадка",        cvar: "--c-size",     share: 0.181, delta: -6, problem: true },
  { key: "quality",  name: "Проблема с качеством товара",            short: "Качество (брак / дефект)", cvar: "--c-quality",  share: 0.168, delta: 12, problem: true },
  { key: "pack",     name: "Проблема с комплектацией / упаковкой",   short: "Комплектация / упаковка",  cvar: "--c-pack",     share: 0.071, delta: 34, problem: true },
  { key: "card",     name: "Несоответствие карточке товара",         short: "Несоответствие карточке",  cvar: "--c-card",     share: 0.060, delta: 9,  problem: true },
  { key: "price",    name: "Цена / ценность",                        short: "Цена / ценность",          cvar: "--c-price",    share: 0.035, delta: 4,  problem: true },
  { key: "return",   name: "Проблема с возвратом",                   short: "Возврат",                  cvar: "--c-return",   share: 0.013, delta: 18, problem: true },
  { key: "delivery", name: "Проблема доставки / получения",          short: "Доставка / получение",     cvar: "--c-delivery", share: 0.005, delta: -1, problem: true },
  { key: "other",    name: "Другая проблема",                        short: "Другое",                   cvar: "--c-other",    share: 0.004, delta: 0,  problem: true },
];

export const CMAP: Record<ClassKey, ClassDef> = Object.fromEntries(
  CLASSES.map((c) => [c.key, c]),
) as Record<ClassKey, ClassDef>;

export const PROBLEMS = CLASSES.filter((c) => c.problem);

export const WEEKS = [
  "04.08", "11.08", "18.08", "25.08", "01.09", "08.09",
  "15.09", "22.09", "29.09", "06.10", "13.10", "20.10",
];

// сид-генератор — стабильная картинка
function seeded(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

function buildSeries(): Record<ClassKey, number[]> {
  const trend: Record<ClassKey, number> = {
    pos: 0.01, size: -0.03, quality: 0.05, pack: 0.09, card: 0.03,
    price: 0.01, return: 0.05, delivery: -0.01, other: 0,
  };
  const rnd = seeded(42);
  const out = {} as Record<ClassKey, number[]>;
  for (const c of CLASSES) {
    const base = c.share * 100;
    out[c.key] = WEEKS.map((_, i) => {
      const t = i / (WEEKS.length - 1);
      const drift = base * trend[c.key] * (t - 0.5) * 2;
      const noise = (rnd() - 0.5) * base * 0.16;
      return Math.max(0.05, +(base + drift + noise).toFixed(2));
    });
  }
  return out;
}

export const SERIES = buildSeries();
// доля негатива = 100 − позитив (НЕ сумма долей: multilabel задвоит)
export const negShareSeries = WEEKS.map((_, i) => +(100 - SERIES.pos[i]).toFixed(1));
export const NEG_SHARE = +(100 - CMAP.pos.share * 100).toFixed(1);

export interface ProductRow {
  name: string;
  brand: string;
  risk: number;
  total: number;
  top: ClassKey[];
}
export const PRODUCTS: ProductRow[] = [
  { name: "Джинсы mom fit, синие", brand: "DENIM CO", risk: 78, total: 1240, top: ["size", "quality"] },
  { name: "Пуховик оверсайз",       brand: "NORDWAY",  risk: 64, total: 980,  top: ["pack", "size"] },
  { name: "Кроссовки беговые W",     brand: "RUNLAB",   risk: 57, total: 1510, top: ["size", "card"] },
  { name: "Платье миди в рубчик",    brand: "BASIC",    risk: 41, total: 760,  top: ["quality", "pack"] },
  { name: "Термокружка 500 мл",      brand: "HOTPACK",  risk: 33, total: 420,  top: ["pack", "return"] },
];

export interface MethodStep { t: string; s: string; ms: string; }
export const METHOD_STEPS: MethodStep[] = [
  { t: "Отобрали отзывы по фильтрам",   s: "период 04.08–20.10, все категории — 48 320 отзывов", ms: "12 мс" },
  { t: "Классификатор проставил метки", s: "bge-m3 + LinearSVC, 9 классов, multilabel (сохранённые пороги)", ms: "факт из БД" },
  { t: "Свернули в доли и динамику",    s: "GROUP BY label, неделя; доля = отзывы_с_меткой / все_отзывы", ms: "34 мс" },
  { t: "Сравнили с прошлым периодом",   s: "дельта = (тек − пред) / пред · 100%", ms: "8 мс" },
];

export interface ReviewItem {
  id: string;
  rating: number;
  prod: string;
  labels: ClassKey[];
  text: string;
  score?: string;
}
export const METHOD_REVIEWS: ReviewItem[] = [
  { id: "rv_8842190", rating: 2, prod: "Пуховик оверсайз",  labels: ["pack", "size"],   text: "Пришло в мятом пакете, один шнурок из капюшона выдернут, упаковка порвана. Сам пуховик нормальный, но осадок неприятный." },
  { id: "rv_8839005", rating: 1, prod: "Пуховик оверсайз",  labels: ["pack"],           text: "Коробка была вскрыта, внутри не было запасных пуговиц, которые обещаны в описании. Верните комплектацию как на фото." },
  { id: "rv_8851277", rating: 3, prod: "Термокружка 500 мл", labels: ["pack", "return"], text: "Крышка пришла отдельно от кружки, резинка помята. Оформлять возврат из-за упаковки не хочется, но неприятно." },
];

// ---------- форматирование ----------
export const fmt = (n: number) => n.toLocaleString("ru-RU");
export const pct = (n: number, d = 1) =>
  n.toLocaleString("ru-RU", { minimumFractionDigits: d, maximumFractionDigits: d }) + "%";

// ---------- цвета (читаем из CSS-переменных → одна тема-источник) ----------
export function cssv(v: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(v).trim();
}
export const col = (key: ClassKey) => cssv(CMAP[key].cvar);

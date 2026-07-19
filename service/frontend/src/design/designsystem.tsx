import { CLASSES, col, cssv } from "./data";

const STATUS: [string, string][] = [
  ["Спад / хорошо", "--good"],
  ["Внимание", "--warning"],
  ["Заметный рост", "--serious"],
  ["Резкий рост / плохо", "--critical"],
];
const TOKENS: [string, string][] = [
  ["--accent", "Акцент (UI)"], ["--plane", "Фон"], ["--surface", "Карточка"], ["--surface-2", "Инсет"],
  ["--border", "Граница"], ["--ink", "Текст"], ["--ink-2", "Текст 2"], ["--ink-3", "Текст 3"],
];

export function DesignSystemView() {
  return (
    <main className="dash">
      <section className="ds">
        <div>
          <h2>Палитра 9 классов</h2>
          <p className="note" style={{ margin: "4px 0 12px" }}>
            Один класс = один цвет во всех графиках. Провалидировано <code>validate_palette.js</code>: CVD-разделение ≥ порога в обеих темах; контраст-исключения закрыты подписями и легендой. Позитив — спокойный аква; две главные проблемы (размер, качество) — тёплые тревожные тона; «Другое» — нейтральный серый.
          </p>
          <div className="swgrid">
            {CLASSES.map((c, i) => (
              <div key={c.key} className="swatch">
                <div className="cap" style={{ background: col(c.key) }} />
                <div className="meta"><b>{c.short}</b><code>{col(c.key)} · слот {i + 1}</code></div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2>Статусные цвета <span className="note" style={{ fontWeight: 400 }}>— состояние, отдельно от классов</span></h2>
          <p className="note" style={{ margin: "4px 0 12px" }}>Рост проблемы = плохо (тёплый/красный), спад = хорошо (зелёный). Всегда со стрелкой и знаком — не цветом одним.</p>
          <div className="swgrid">
            {STATUS.map(([name, v]) => (
              <div key={v} className="swatch"><div className="cap" style={{ background: cssv(v) }} /><div className="meta"><b>{name}</b><code>{cssv(v)}</code></div></div>
            ))}
          </div>
        </div>

        <div>
          <h2>Типографика</h2>
          <div className="typ">
            <div style={{ fontSize: 29, fontWeight: 700, letterSpacing: "-.02em" }}>48 320 <span style={{ fontSize: 15, color: "var(--ink-3)" }}>— цифра-факт, tabular-nums</span></div>
            <div style={{ fontSize: 17, fontWeight: 650 }}>Заголовок карточки — 15–17px / 650</div>
            <div style={{ fontSize: 14 }}>Основной текст — 14px / 1.45. Системный sans без вебфонтов: быстро, надёжно, читаемо на любой платформе.</div>
            <div className="eyebrow">НАДЗАГОЛОВОК · 11px · uppercase · +tracking</div>
            <div className="note">Один шрифт (system-ui). Для дата-инструмента характерный дисплейный шрифт — лишний «шум»; точность важнее декора.</div>
          </div>
        </div>

        <div>
          <h2>Токены темы</h2>
          <p className="note" style={{ margin: "4px 0 12px" }}>Нейтрали со слабым сине-фиолетовым уклоном (выбраны, не дефолтный серый). Обе темы описаны на уровне токенов — переключаются в одном месте.</p>
          <div className="toklist">
            {TOKENS.map(([v, name]) => (
              <div key={v} className="tok"><span className="box" style={{ background: cssv(v) }} />{name}<code>{v}</code></div>
            ))}
          </div>
        </div>

        <div>
          <h2>Разделение «факт ↔ гипотеза»</h2>
          <p className="note" style={{ margin: "4px 0 10px" }}>
            Числа из БД помечены <span className="fact-tag">● Факт из БД</span>, объяснения ИИ — <span className="fact-tag hyp">◇ Гипотеза</span> с обязательной ссылкой на отзывы-подтверждения (review_id). Это ключ к доверию продавца.
          </p>
        </div>
      </section>
    </main>
  );
}

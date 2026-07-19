import { useEffect, useRef, useState, type ReactNode } from "react";
import { CMAP } from "./design/data";
import type { QueryCtx } from "./design/answers";
import { DashboardView } from "./design/dashboard";
import { ChatView, type ChatHandle } from "./design/chat";
import { ScenariosView } from "./design/scenarios";
import { DesignSystemView } from "./design/designsystem";

type View = "dash" | "chat" | "scen" | "ds";
type ThemeMode = "auto" | "light" | "dark";

const TITLES: Record<View, [string, string]> = {
  dash: ["Дашборд", "обзор проблем в отзывах"],
  chat: ["Чат", "свободный вопрос · drill-down"],
  scen: ["Сценарии", "готовые отчёты в один клик"],
  ds: ["Дизайн-система", "палитра · типографика · токены"],
};

function derive(ctx: QueryCtx): { q: string; ctxLabel: string } {
  const c = ctx.label ? CMAP[ctx.label] : null;
  if (ctx.intent === "problem_growth_analysis" && c)
    return { q: `Почему выросли жалобы «${c.short}» (${c.delta > 0 ? "+" : ""}${c.delta}%)?`, ctxLabel: `Контекст: рост «${c.short}»` };
  if (ctx.intent === "review_examples" && c)
    return { q: `Покажи отзывы с проблемой «${c.short}» и объясни суть`, ctxLabel: `Контекст: «${c.short}»` };
  if (ctx.product) return { q: `Какие главные проблемы у товара «${ctx.product}»?`, ctxLabel: `Контекст: ${ctx.product}` };
  return { q: "Расскажи подробнее", ctxLabel: "Контекст с дашборда" };
}

export function App() {
  const initialView = ((): View => {
    const h = typeof location !== "undefined" ? location.hash.replace("#", "") : "";
    return (["dash", "chat", "scen", "ds"] as View[]).includes(h as View) ? (h as View) : "dash";
  })();
  const [view, setView] = useState<View>(initialView);
  const [themeMode, setThemeMode] = useState<ThemeMode>("auto");
  const [gran, setGran] = useState<"day" | "week" | "month">("week");
  const [drill, setDrill] = useState<{ text: string; ctx: QueryCtx } | null>(null);
  const drillTimer = useRef<number | undefined>(undefined);
  const chatRef = useRef<ChatHandle>(null);

  useEffect(() => {
    if (!drill) return;
    window.clearTimeout(drillTimer.current);
    drillTimer.current = window.setTimeout(() => setDrill(null), 4200);
    return () => window.clearTimeout(drillTimer.current);
  }, [drill]);

  function cycleTheme() {
    const next: ThemeMode = themeMode === "auto" ? "light" : themeMode === "light" ? "dark" : "auto";
    if (next === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", next);
    setThemeMode(next);
  }

  function openDrill(text: string, ctx: QueryCtx) { setDrill({ text, ctx }); }
  function drillGo() {
    if (!drill) return;
    const { q, ctxLabel } = derive(drill.ctx);
    setView("chat");
    chatRef.current?.fill(q, ctxLabel, drill.ctx);
    setDrill(null);
  }
  function chatSeed(ctx: QueryCtx) {
    const { q, ctxLabel } = derive(ctx);
    setView("chat");
    chatRef.current?.fill(q, ctxLabel, ctx);
  }
  function chatAsk(q: string, ctx?: QueryCtx) {
    setView("chat");
    chatRef.current?.send(q, ctx);
  }
  function scenOpenChat(q?: string, ctx?: QueryCtx) {
    setView("chat");
    if (q) chatRef.current?.send(q, ctx);
  }

  const themeLbl = { auto: "Авто", light: "Светлая", dark: "Тёмная" }[themeMode];

  return (
    <div className="app">
      {/* ---------- RAIL ---------- */}
      <aside className="rail">
        <div className="brand">
          <div className="mark">ОА</div>
          <div><b>Отзывы · Аналитика</b><small>Wildberries · продавцу</small></div>
        </div>

        <div className="nav-group">
          <div className="eyebrow">Обзор</div>
          <NavItem active={view === "dash"} onClick={() => setView("dash")} label="Дашборд" icon={<IconDash />} />
          <NavItem active={view === "chat"} onClick={() => setView("chat")} label="Чат" icon={<IconChat />} />
          <NavItem active={view === "scen"} onClick={() => setView("scen")} label="Сценарии" icon={<IconScen />} />
        </div>
        <div className="nav-group">
          <div className="eyebrow">Система</div>
          <NavItem active={view === "ds"} onClick={() => setView("ds")} label="Дизайн-система" icon={<IconDs />} />
        </div>

        <div className="rail-foot">
          <button className="theme-btn" onClick={cycleTheme}><span>Тема</span><span>{themeLbl}</span></button>
        </div>
      </aside>

      {/* ---------- MAIN ---------- */}
      <div className="main">
        <div className="topbar">
          <h1>{TITLES[view][0]} <small>{TITLES[view][1]}</small></h1>
          {view === "dash" && (
            <div className="seg">
              {(["day", "week", "month"] as const).map((g) => (
                <button key={g} className={gran === g ? "active" : ""} onClick={() => setGran(g)}>
                  {{ day: "День", week: "Неделя", month: "Месяц" }[g]}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className={view === "dash" ? "" : "hidden"}>
          <DashboardView gran={gran} onDrill={openDrill} onChatSeed={chatSeed} onChatAsk={chatAsk} />
        </div>
        <div className={view === "chat" ? "" : "hidden"}>
          <ChatView ref={chatRef} />
        </div>
        <div className={view === "scen" ? "" : "hidden"}>
          <ScenariosView onOpenChat={scenOpenChat} />
        </div>
        <div className={view === "ds" ? "" : "hidden"}>
          <DesignSystemView />
        </div>
      </div>

      {/* ---------- глобальные оверлеи ---------- */}
      <div className="tip" id="tip" />
      <div className={"drill" + (drill ? " on" : "")}>
        <span dangerouslySetInnerHTML={{ __html: drill ? `<b>${drill.text}</b> → уйдёт в чат с этим контекстом` : "" }} />
        <button className="go" onClick={drillGo}>Открыть в чате →</button>
      </div>
    </div>
  );
}

// ---------- мелкие компоненты ----------
function NavItem({ active, onClick, label, icon }: { active: boolean; onClick: () => void; label: string; icon: ReactNode }) {
  return (
    <button className={"nav-item" + (active ? " active" : "")} onClick={onClick} type="button">
      {icon}{label}
    </button>
  );
}

const IconDash = () => (
  <svg className="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="1.5" y="1.5" width="5.5" height="6.5" rx="1.2" /><rect x="9" y="1.5" width="5.5" height="4" rx="1.2" /><rect x="9" y="7" width="5.5" height="7.5" rx="1.2" /><rect x="1.5" y="10" width="5.5" height="4.5" rx="1.2" /></svg>
);
const IconChat = () => (
  <svg className="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v6A1.5 1.5 0 0 1 12.5 11H6l-3 3v-3H3.5A1.5 1.5 0 0 1 2 9.5z" /></svg>
);
const IconScen = () => (
  <svg className="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="1.6" y="1.6" width="5.4" height="5.4" rx="1.2" /><rect x="9" y="1.6" width="5.4" height="5.4" rx="1.2" /><rect x="1.6" y="9" width="5.4" height="5.4" rx="1.2" /><rect x="9" y="9" width="5.4" height="5.4" rx="1.2" /></svg>
);
const IconDs = () => (
  <svg className="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="5" cy="5" r="3" /><circle cx="11" cy="11" r="3" /><path d="M5 8v3M8 5h3" /></svg>
);

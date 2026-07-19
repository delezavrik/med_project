import { useState, type ReactNode } from "react";
import {
  AnswerCard, ansTop, ansGrowth, ansDynamics, ansCompare, ansProducts, ansRag,
  type AnswerSpec, type QueryCtx,
} from "./answers";
import { PreviewBars, PreviewLine, PreviewDots } from "./charts";

const ICON = (
  <svg className="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 8h4l2-5 3 10 2-5h1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface Scenario { key: string; title: string; sub: string; tag: string; gen: () => AnswerSpec; preview: ReactNode; }

const SCENARIOS: Scenario[] = [
  { key: "top",      title: "Топ проблем и доли",      sub: "самые частые проблемы за период",   tag: "обзор",     gen: ansTop,      preview: <PreviewBars keys={["size", "quality", "pack", "card"]} /> },
  { key: "growth",   title: "Что выросло сейчас",       sub: "резкий рост к прошлому периоду",     tag: "алерт",     gen: ansGrowth,   preview: <PreviewLine keyName="pack" /> },
  { key: "dynamics", title: "Динамика негатива",        sub: "как менялась доля проблем по неделям", tag: "тренд",   gen: ansDynamics, preview: <PreviewLine keyName="__neg" /> },
  { key: "compare",  title: "Сравнение периодов",       sub: "этот период против прошлого",        tag: "сравнение", gen: ansCompare,  preview: <PreviewBars keys={["pack", "return", "quality", "size"]} signed /> },
  { key: "products", title: "Топ товаров по проблеме",  sub: "где проблема встречается чаще",       tag: "риск",      gen: ansProducts, preview: <PreviewBars keys={["size", "quality", "pack", "return"]} /> },
  { key: "rag",      title: "Похожие отзывы (RAG)",     sub: "поиск по смыслу, не по слову",       tag: "RAG",       gen: ansRag,      preview: <PreviewDots /> },
];

export function ScenariosView({ onOpenChat }: { onOpenChat: (q?: string, ctx?: QueryCtx) => void }) {
  const [selected, setSelected] = useState<Scenario | null>(null);

  if (selected) {
    return (
      <main className="dash">
        <div className="report-top">
          <button className="back" onClick={() => setSelected(null)}>← Сценарии</button>
          <div className="t"><h2>{selected.title}</h2><div className="sub">{selected.sub} · период 04.08–20.10.2025</div></div>
        </div>
        <AnswerCard spec={selected.gen()} onAsk={(q, ctx) => onOpenChat(q, ctx)} />
        <div className="report-note">
          Нужно копнуть глубже или спросить своими словами?
          <button className="btn" onClick={() => onOpenChat()}>Открыть в чате</button>
        </div>
      </main>
    );
  }

  return (
    <main className="dash">
      <div className="scen-head"><h2>Сценарии</h2><p className="note">Готовые отчёты в один клик. Нужен свободный вопрос своими словами — раздел «Чат».</p></div>
      <div className="scen-cards">
        {SCENARIOS.map((s) => (
          <button key={s.key} className="scard" onClick={() => { setSelected(s); window.scrollTo({ top: 0 }); }}>
            <div className="thumb">{s.preview}</div>
            <div className="cbody">
              <div className="ct">{ICON}{s.title}</div>
              <div className="cs">{s.sub}</div>
              <div className="cmeta"><span className="tg">{s.tag}</span>факт из БД</div>
            </div>
          </button>
        ))}
      </div>
    </main>
  );
}

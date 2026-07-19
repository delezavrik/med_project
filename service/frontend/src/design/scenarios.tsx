import { useEffect, useState, type ReactNode } from "react";
import { askChat, type AnswerResponse } from "./api";
import { AnswerView } from "./answerview";
import { PreviewBars, PreviewLine, PreviewDots } from "./charts";

const ICON = (
  <svg className="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 8h4l2-5 3 10 2-5h1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface Scenario { key: string; title: string; sub: string; tag: string; message: string; preview: ReactNode; }

const SCENARIOS: Scenario[] = [
  { key: "top",      title: "Топ проблем и доли",     sub: "самые частые проблемы за период",   tag: "обзор",     message: "Покажи топ проблем в отзывах",                    preview: <PreviewBars keys={["size", "quality", "pack", "card"]} /> },
  { key: "growth",   title: "Что выросло сейчас",      sub: "резкий рост к прошлому периоду",     tag: "алерт",     message: "Что сильнее всего выросло и почему? Объясни по отзывам", preview: <PreviewLine keyName="pack" /> },
  { key: "dynamics", title: "Динамика негатива",       sub: "как менялась доля проблем по неделям", tag: "тренд",   message: "Покажи динамику проблем по неделям",              preview: <PreviewLine keyName="__neg" /> },
  { key: "rag",      title: "Похожие отзывы (RAG)",    sub: "смысловой поиск по векторам bge-m3",  tag: "RAG",       message: "Похожие отзывы про порванную упаковку и повреждённую коробку", preview: <PreviewDots /> },
  { key: "products", title: "Топ товаров по проблеме", sub: "где проблема встречается чаще",       tag: "риск",      message: "Топ товаров с проблемой качества",                preview: <PreviewBars keys={["size", "quality", "pack", "return"]} /> },
  { key: "quality",  title: "Разбор качества",         sub: "почему жалуются на брак/дефект",      tag: "разбор",    message: "Почему жалуются на качество товара? Разбери по отзывам", preview: <PreviewDots /> },
];

function Report({ scenario, onOpenChat }: { scenario: Scenario; onOpenChat: (q?: string) => void }) {
  const [resp, setResp] = useState<AnswerResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    askChat(scenario.message)
      .then((r) => { if (!cancelled) { setResp(r); setStatus("ready"); } })
      .catch(() => { if (!cancelled) setStatus("error"); });
    return () => { cancelled = true; };
  }, [scenario.message]);

  return (
    <>
      {status === "loading" && (
        <div className="answer"><div className="lead"><p>Считаю по базе… <span className="typing"><i /><i /><i /></span></p></div></div>
      )}
      {status === "error" && (
        <div className="answer"><div className="lead"><p>Не удалось построить отчёт. Проверьте бэкенд и попробуйте снова.</p></div></div>
      )}
      {status === "ready" && resp && <AnswerView resp={resp} />}
      <div className="report-note">
        Нужно копнуть глубже или спросить своими словами?
        <button className="btn" onClick={() => onOpenChat(scenario.message)}>Открыть в чате</button>
      </div>
    </>
  );
}

export function ScenariosView({ onOpenChat }: { onOpenChat: (q?: string) => void }) {
  const [selected, setSelected] = useState<Scenario | null>(null);

  if (selected) {
    return (
      <main className="dash">
        <div className="report-top">
          <button className="back" onClick={() => setSelected(null)}>← Сценарии</button>
          <div className="t"><h2>{selected.title}</h2><div className="sub">{selected.sub}</div></div>
        </div>
        <Report scenario={selected} onOpenChat={onOpenChat} />
      </main>
    );
  }

  return (
    <main className="dash">
      <div className="scen-head"><h2>Сценарии</h2><p className="note">Готовые отчёты в один клик — считаются по реальной базе. Нужен свободный вопрос — раздел «Чат».</p></div>
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

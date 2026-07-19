import {
  forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState,
} from "react";
import { AnswerCard, route, type AnswerSpec, type QueryCtx } from "./answers";

const CHAT_EXAMPLES = [
  "Почему выросли жалобы на упаковку?",
  "Топ проблем у пуховиков",
  "Сравни сентябрь с августом",
];

interface Msg { id: number; role: "user" | "bot"; text?: string; greeting?: boolean; spec?: AnswerSpec; typing?: boolean; }

export interface ChatHandle {
  fill: (text: string, ctxLabel: string, ctx: QueryCtx) => void;
  send: (text: string, ctx?: QueryCtx) => void;
}

export const ChatView = forwardRef<ChatHandle>(function ChatView(_props, ref) {
  const [msgs, setMsgs] = useState<Msg[]>([{ id: 0, role: "bot", greeting: true }]);
  const [input, setInput] = useState("");
  const [ctxChip, setCtxChip] = useState<string | null>(null);
  const pendingCtx = useRef<QueryCtx>({});
  const idc = useRef(1);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const scrollEnd = () => requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }));

  function ask(text: string, ctx: QueryCtx = {}) {
    const t = text.trim();
    if (!t) return;
    const botId = idc.current + 1;
    setMsgs((prev) => [
      ...prev,
      { id: idc.current, role: "user", text: t },
      { id: botId, role: "bot", typing: true },
    ]);
    idc.current += 2;
    setCtxChip(null);
    pendingCtx.current = {};
    scrollEnd();
    window.setTimeout(() => {
      const spec = route(t, ctx);
      setMsgs((prev) => prev.map((m) => (m.id === botId ? { ...m, typing: false, spec } : m)));
      scrollEnd();
    }, 720);
  }

  useImperativeHandle(ref, () => ({
    fill(text, ctxLabel, ctx) {
      setInput(text);
      setCtxChip(ctxLabel);
      pendingCtx.current = ctx;
      requestAnimationFrame(() => taRef.current?.focus());
    },
    send(text, ctx) { ask(text, ctx); },
  }));

  useLayoutEffect(() => {
    const ta = taRef.current;
    if (ta) { ta.style.height = "auto"; ta.style.height = Math.min(140, ta.scrollHeight) + "px"; }
  }, [input]);

  return (
    <main className="dash chat-dash">
      <div className="thread">
        {msgs.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="msg user"><div className="bubble-user">{m.text}</div></div>
          ) : (
            <div key={m.id} className="msg bot">
              <div className="bot-head">
                <span className="av">ИИ</span>
                Аналитик отзывов
                {m.spec?.ms && <> · <span style={{ color: "var(--good-ink)" }}>{m.spec.ms}</span></>}
                {m.typing && <span className="typing"><i /><i /><i /></span>}
              </div>
              {m.greeting && (
                <div className="answer"><div className="lead">
                  <p>Спросите про отзывы своими словами. Я отвечу числами <span className="fact-tag">● Факт из БД</span>, а если попросите объяснить — добавлю гипотезу <span className="fact-tag hyp">◇</span> со ссылкой на конкретные отзывы. Готовые отчёты — в разделе «Сценарии».</p>
                  <div style={{ marginTop: 4 }}>
                    {CHAT_EXAMPLES.map((q) => <button key={q} className="chip-ex" onClick={() => ask(q)}>{q}</button>)}
                  </div>
                </div></div>
              )}
              {m.spec && <AnswerCard spec={m.spec} onAsk={(q, ctx) => ask(q, ctx)} />}
            </div>
          ),
        )}
        <div ref={endRef} />
      </div>

      <div className="composer-wrap">
        {ctxChip && (
          <div className="ctx-chip">↳ {ctxChip} <button title="Убрать" onClick={() => { setCtxChip(null); pendingCtx.current = {}; }}>✕</button></div>
        )}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(input, pendingCtx.current); setInput(""); }}>
          <textarea
            ref={taRef} rows={1} value={input}
            placeholder="Спросите про отзывы: «почему выросли жалобы на упаковку?»"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input, pendingCtx.current); setInput(""); } }}
          />
          <button className="send" type="submit" title="Спросить">
            <svg width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2 8h10M8 4l4 4-4 4" /></svg>
          </button>
        </form>
        <div className="composer-note">Свободный вопрос своими словами. Готовые пресеты — в разделе «Сценарии». Числа — факт из БД, объяснения — гипотеза со ссылкой на отзывы.</div>
      </div>
    </main>
  );
});

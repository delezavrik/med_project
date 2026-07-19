import {
  forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState,
} from "react";
import { askChat, type AnswerResponse } from "./api";
import { AnswerView } from "./answerview";

const CHAT_EXAMPLES = [
  "Почему выросли жалобы на упаковку?",
  "Топ проблем в отзывах",
  "Похожие отзывы про порванную упаковку и вмятину на коробке",
];

interface Msg { id: number; role: "user" | "bot"; text?: string; greeting?: boolean; resp?: AnswerResponse; loading?: boolean; error?: string; }

export interface ChatHandle {
  fill: (text: string, ctxLabel: string) => void;
  send: (text: string) => void;
}

export const ChatView = forwardRef<ChatHandle>(function ChatView(_props, ref) {
  const [msgs, setMsgs] = useState<Msg[]>([{ id: 0, role: "bot", greeting: true }]);
  const [input, setInput] = useState("");
  const [ctxChip, setCtxChip] = useState<string | null>(null);
  const idc = useRef(1);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const scrollEnd = () => requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }));

  function ask(text: string) {
    const t = text.trim();
    if (!t) return;
    const botId = idc.current + 1;
    setMsgs((prev) => [...prev, { id: idc.current, role: "user", text: t }, { id: botId, role: "bot", loading: true }]);
    idc.current += 2;
    setCtxChip(null);
    scrollEnd();
    askChat(t)
      .then((resp) => setMsgs((prev) => prev.map((m) => (m.id === botId ? { ...m, loading: false, resp } : m))))
      .catch(() => setMsgs((prev) => prev.map((m) => (m.id === botId ? { ...m, loading: false, error: "Не удалось получить ответ. Проверьте, что бэкенд запущен, и попробуйте ещё раз." } : m))))
      .finally(scrollEnd);
  }

  useImperativeHandle(ref, () => ({
    fill(text, ctxLabel) { setInput(text); setCtxChip(ctxLabel); requestAnimationFrame(() => taRef.current?.focus()); },
    send(text) { ask(text); },
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
                {m.resp?.execution_ms != null && <> · <span style={{ color: "var(--good-ink)" }}>{Math.round(m.resp.execution_ms)} мс</span></>}
                {m.loading && <span className="typing"><i /><i /><i /></span>}
              </div>
              {m.greeting && (
                <div className="answer"><div className="lead">
                  <p>Спросите про отзывы своими словами. Отвечаю числами <span className="fact-tag">● Факт из БД</span>, а на «почему»/«объясни» добавляю разбор <span className="fact-tag hyp">◇</span> со ссылкой на конкретные отзывы (review_id). Готовые отчёты — в разделе «Сценарии».</p>
                  <div style={{ marginTop: 4 }}>
                    {CHAT_EXAMPLES.map((q) => <button key={q} className="chip-ex" onClick={() => ask(q)}>{q}</button>)}
                  </div>
                </div></div>
              )}
              {m.error && <div className="answer"><div className="lead"><p>{m.error}</p></div></div>}
              {m.resp && <AnswerView resp={m.resp} />}
            </div>
          ),
        )}
        <div ref={endRef} />
      </div>

      <div className="composer-wrap">
        {ctxChip && (
          <div className="ctx-chip">↳ {ctxChip} <button title="Убрать" onClick={() => setCtxChip(null)}>✕</button></div>
        )}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(input); setInput(""); }}>
          <textarea
            ref={taRef} rows={1} value={input}
            placeholder="Спросите про отзывы: «почему выросли жалобы на упаковку?»"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input); setInput(""); } }}
          />
          <button className="send" type="submit" title="Спросить">
            <svg width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2 8h10M8 4l4 4-4 4" /></svg>
          </button>
        </form>
        <div className="composer-note">Свободный вопрос своими словами. Числа — факт из PostgreSQL, объяснения — LLM-разбор со ссылкой на отзывы. Ответ обычно 3–10 сек.</div>
      </div>
    </main>
  );
});

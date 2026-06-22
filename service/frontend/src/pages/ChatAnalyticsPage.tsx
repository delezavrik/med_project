import { useState } from "react";
import { askChat } from "../api/client";
import type { AnswerResponse } from "../api/types";

export function ChatAnalyticsPage() {
  const [message, setMessage] = useState("Сколько было жалоб на доставку у книг?");
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      setResult(await askChat({ message }));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Чат с аналитиком</h1>
      <form onSubmit={handleSubmit}>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} />
        <button type="submit" disabled={loading}>{loading ? "Думаю..." : "Спросить"}</button>
      </form>

      {result && (
        <section>
          <h2>Ответ</h2>
          <p>{result.answer_text}</p>
          <pre>{JSON.stringify(result.parsed_query, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}

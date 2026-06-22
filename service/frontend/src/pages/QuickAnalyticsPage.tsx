import { useState } from "react";
import type { AnswerResponse } from "../api/types";
import { QuickAnalyticsForm } from "../components/QuickAnalyticsForm";

export function QuickAnalyticsPage() {
  const [result, setResult] = useState<AnswerResponse | null>(null);

  return (
    <main>
      <h1>Быстрая аналитика</h1>
      <QuickAnalyticsForm onResult={setResult} />

      {result && (
        <section>
          <h2>Ответ</h2>
          <p>{result.answer_text}</p>
          <pre>{JSON.stringify(result.ui_blocks, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}

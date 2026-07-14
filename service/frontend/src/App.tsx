import { useState } from "react";
import { ChatAnalyticsPage } from "./pages/ChatAnalyticsPage";
import { QuickAnalyticsPage } from "./pages/QuickAnalyticsPage";

type Page = "quick" | "chat";

export function App() {
  const [page, setPage] = useState<Page>("quick");

  return (
    <>
      <header className="app-header">
        <div>
          <span className="app-mark">RA</span>
          <strong>Reviews Analytics</strong>
        </div>
        <nav className="tabs" aria-label="Разделы">
          <button className={page === "quick" ? "active" : ""} type="button" onClick={() => setPage("quick")}>
            Сценарии
          </button>
          <button className={page === "chat" ? "active" : ""} type="button" onClick={() => setPage("chat")}>
            Чат
          </button>
        </nav>
      </header>

      {page === "quick" ? <QuickAnalyticsPage /> : <ChatAnalyticsPage />}
    </>
  );
}

import { useEffect, useState } from "react";

interface Props {
  loading: boolean;
  startedAt: number | null;
  estimate: string;
}

export function RequestProgress({ loading, startedAt, estimate }: Props) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!loading) {
      return;
    }

    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [loading]);

  if (!loading || startedAt === null) {
    return null;
  }

  const elapsedSeconds = Math.max(0, (now - startedAt) / 1000);

  return (
    <div className="request-progress" role="status" aria-live="polite">
      <div>
        <strong>Выполняю запрос</strong>
        <span>Прошло {formatSeconds(elapsedSeconds)}</span>
      </div>
      <div>
        <strong>Ожидание</strong>
        <span>{estimate}</span>
      </div>
    </div>
  );
}

export function formatDuration(ms?: number | null) {
  if (ms === null || ms === undefined) {
    return null;
  }
  return formatSeconds(ms / 1000);
}

function formatSeconds(seconds: number) {
  if (seconds < 1) {
    return "<1 сек";
  }
  if (seconds < 60) {
    return `${Math.round(seconds)} сек`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return rest ? `${minutes} мин ${rest} сек` : `${minutes} мин`;
}

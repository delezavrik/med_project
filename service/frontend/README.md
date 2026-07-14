# frontend — UI для проверки аналитики отзывов

Это полноценный Vite/React-интерфейс для MVP-сервиса.

## Запуск

Frontend запускается через общий Docker Compose из папки `service/`.

```bash
cd service
cp backend/.env.docker.example backend/.env
docker compose -f docker-compose.dev.yml up --build
```

Frontend откроется на:

```text
http://localhost:5173
```

Vite проксирует `/api/*` в backend.

Проверить production-сборку frontend без локального Node можно так:

```bash
docker compose -f docker-compose.dev.yml build frontend-build
```

## Что есть в UI

- вкладка `Сценарии` для всех PostgreSQL-шаблонов;
- вкладка `Чат` для `/api/v1/chat/ask`;
- фильтры по периоду, категории, бренду, товару и рейтингу;
- отдельный режим выбора подмножества проблем для сценариев вроде `top_problems`;
- таблицы, метрики, предупреждения и примеры отзывов без raw JSON на первом экране;
- details-блок с `ParsedQuery` и raw-данными для отладки.

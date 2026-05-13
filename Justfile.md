# AI Reality Map / Go — Backend

Социальная карта города с AI-разметкой вайба заведений, чек-инами,
знакомствами и геймификацией. Pre-MVP (Этап 0): Астана, демо-флоу
из 50 заведений и 10 событий.

Стек: Django 5 + DRF, PostgreSQL 16 + PostGIS + pgvector, Celery + Redis,
Cloudflare R2 для медиа, Gemini для AI.

## Требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — пакетный менеджер
- [just](https://github.com/casey/just) — task runner
- Docker + Docker Compose

## С нуля до запуска

```bash
git clone <repo>
cd backend
just setup     # зависимости + .env + docker + миграции + seed
just start     # web + worker + beat в фоне
```

После `just start`:
- API: <http://localhost:8000/api/>
- Swagger UI: <http://localhost:8000/api/docs/>
- Admin: <http://localhost:8000/admin/> (создай через `just createsuperuser`)

Остановить всё: `just stop`. Логи: `just logs web` / `worker` / `beat`.

Перед первым запуском проверь `.env` — нужны как минимум `SECRET_KEY`,
`DATABASE_URL`, `REDIS_URL`. Для AI — `GEMINI_API_KEY`, для геокодинга
— `MAPBOX_ACCESS_TOKEN`.

## Команды `just`

`just` без аргументов — список всех рецептов с описаниями.

### Главные

| Команда | Описание |
|---|---|
| `just setup` | **Первый запуск.** Зависимости + .env + docker + миграции + seed |
| `just start` | Поднять весь стек (docker + web + worker + beat) в фоне |
| `just stop` | Остановить всё (процессы + docker) |
| `just logs <web\|worker\|beat>` | Логи фонового процесса. По умолчанию `web` |

### Foreground dev (по отдельности)

Когда хочется видеть логи прямо в терминале — запускай в разных окнах.

| Команда | Описание |
|---|---|
| `just dev` | Docker + dev-сервер (foreground) |
| `just runserver` | Только dev-сервер (docker должен быть поднят) |
| `just worker` | Celery worker (foreground) |
| `just beat` | Celery beat (foreground) |
| `just docker-up` | Только Postgres + Redis |
| `just docker-down` | Остановить контейнеры |
| `just docker-logs` | Логи Postgres + Redis |

### Django management

| Команда | Описание |
|---|---|
| `just check` | `manage.py check` — конфиг, модели, миграции |
| `just check-migrations` | Проверить нужны ли новые миграции |
| `just createsuperuser` | Создать суперюзера |
| `just shell` | Django shell (`shell_plus` если установлен) |
| `just dbshell` | psql к локальной БД |

### Миграции

| Команда | Описание |
|---|---|
| `just makemigrations` | Сгенерировать миграции для всех app |
| `just makemigrations users` | Только для конкретного app |
| `just makemigrations-empty users` | Пустая миграция (для RunSQL/RunPython) |
| `just migrate` | Применить все миграции |
| `just migrate-back users 0003` | Откатить app до миграции 0003 |
| `just showmigrations` | Статус миграций |
| `just reset-db` | flush + migrate + seed (структура остаётся) |

### Тесты и качество

| Команда | Описание |
|---|---|
| `just test` | Все тесты |
| `just test apps/users` | Только указанный путь |
| `just test -k checkin` | По паттерну имени |
| `just test-cov` | Тесты + HTML coverage в `htmlcov/` |
| `just lint` | ruff check + format check |
| `just format` | ruff fix + ruff format (автофиксы) |
| `just typecheck` | mypy (отдельно, прогонять руками) |
| `just check-all` | lint + test, для pre-commit |

### Сид данных

| Команда | Описание |
|---|---|
| `just seed` | 50 мест + 10 событий из `fixtures/` |
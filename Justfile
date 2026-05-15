# Justfile
set dotenv-load := true

default:
    @just --list

# --- Setup ---

# Полная установка с нуля: зависимости + docker + .env + миграции + сид
# Используется после клонирования репо. После — `just start`.
setup:
    @echo "📦 Устанавливаю зависимости..."
    uv sync --all-extras
    @echo "🔧 Создаю .env из примера (если нет)..."
    @test -f .env || cp .env.example .env
    @echo "🐳 Поднимаю Postgres + Redis..."
    docker compose --env-file .env -f deploy/docker-compose.yml up -d
    @echo "⏳ Жду пока БД поднимется..."
    @sleep 3
    @echo "🗃️  Применяю миграции..."
    uv run python manage.py migrate
    @echo "🌱 Сидую тестовые данные..."
    just seed
    @echo "✅ Готово. Запусти: just start"

# --- Start everything ---

# Запустить весь стек: docker + web + worker + beat в фоне
# Логи: `just logs`. Остановить: `just stop`.
start:
    docker compose --env-file .env -f deploy/docker-compose.yml up -d
    @echo "🚀 Запускаю web + worker + beat..."
    @mkdir -p .runtime
    @uv run python manage.py runserver 0.0.0.0:8000 > .runtime/web.log 2>&1 & echo $! > .runtime/web.pid
    @uv run celery -A config worker -l info -Q default,media,ai > .runtime/worker.log 2>&1 & echo $! > .runtime/worker.pid
    @uv run celery -A config beat -l info > .runtime/beat.log 2>&1 & echo $! > .runtime/beat.pid
    @echo "✅ Поднято. Логи: just logs <web|worker|beat>. Стоп: just stop"

# Запустить стек с реальной отправкой email через SMTP
start-smtp:
    @DJANGO_EMAIL_REAL=true just start

# Остановить все процессы (web, worker, beat) и docker
stop:
    @echo "🛑 Останавливаю процессы..."
    @-test -f .runtime/web.pid && kill `cat .runtime/web.pid` 2>/dev/null && rm .runtime/web.pid || true
    @-test -f .runtime/worker.pid && kill `cat .runtime/worker.pid` 2>/dev/null && rm .runtime/worker.pid || true
    @-test -f .runtime/beat.pid && kill `cat .runtime/beat.pid` 2>/dev/null && rm .runtime/beat.pid || true
    docker compose --env-file .env -f deploy/docker-compose.yml down
    @echo "✅ Стоп"

# Показать логи: just logs web | worker | beat
logs target="web":
    tail -f .runtime/{{target}}.log

# --- Foreground dev (по отдельности, в нескольких терминалах) ---

# Только dev-сервер (docker должен быть поднят отдельно через just docker-up)
runserver:
    uv run python manage.py runserver 0.0.0.0:8000

# Docker + dev-сервер (foreground)
dev:
    docker compose --env-file .env -f deploy/docker-compose.yml up -d
    uv run python manage.py runserver 0.0.0.0:8000

# Celery worker (foreground, 3 очереди: default, media, ai)
worker:
    uv run celery -A config worker -l info -Q default,media,ai

# Celery beat scheduler (foreground)
beat:
    uv run celery -A config beat -l info

# --- Django management ---

# Django system checks — конфиг, модели, миграции
check:
    uv run python manage.py check

# Проверить нужны ли новые миграции (без создания)
check-migrations:
    uv run python manage.py makemigrations --check --dry-run

# Создать суперюзера
createsuperuser:
    uv run python manage.py createsuperuser

# Django shell (shell_plus если есть, иначе обычный)
shell:
    uv run python manage.py shell_plus || uv run python manage.py shell

# psql к локальной БД
dbshell:
    uv run python manage.py dbshell

# --- Migrations ---

# Сгенерировать миграции (можно с именем app: just makemigrations users)
makemigrations *args:
    uv run python manage.py makemigrations {{args}}

# Создать пустую миграцию для app (для RunSQL/RunPython)
makemigrations-empty app:
    uv run python manage.py makemigrations --empty {{app}}

# Применить все миграции
migrate:
    uv run python manage.py migrate

# Откатить миграцию: just migrate-back users 0003
migrate-back app migration:
    uv run python manage.py migrate {{app}} {{migration}}

# Показать статус миграций (применённые/нет)
showmigrations:
    uv run python manage.py showmigrations

# Сбросить данные локальной БД и пересидить (структура остаётся)
reset-db:
    uv run python manage.py flush --noinput
    uv run python manage.py migrate
    just seed

# --- Tests / quality ---

# Запустить тесты (можно с аргументами: just test apps/users)
test *args:
    uv run pytest {{args}}

# Тесты с HTML coverage report
test-cov:
    uv run pytest --cov=apps --cov-report=html --cov-report=term

# Быстрый линт: ruff check + format check
lint:
    uv run ruff check .
    uv run ruff format --check .

# Mypy — отдельно, прогонять руками когда нужно
typecheck:
    uv run mypy apps config

# Автоматический fix + форматирование
format:
    uv run ruff check --fix .
    uv run ruff format .

# Полный pre-commit чек: lint + test
check-all: lint test

# --- Seed ---

# Сидинг тестовых данных (50 мест + 10 событий)
seed:
    uv run python manage.py seed_places
    uv run python manage.py seed_events
    uv run python manage.py seed_achievements

seed-achievements:
    uv run python manage.py seed_achievements

# --- Docker ---

# Поднять только postgres + redis
docker-up:
    docker compose --env-file .env -f deploy/docker-compose.yml up -d

# Остановить контейнеры
docker-down:
    docker compose --env-file .env -f deploy/docker-compose.yml down

# Логи postgres + redis
docker-logs:
    docker compose --env-file .env -f deploy/docker-compose.yml logs -f
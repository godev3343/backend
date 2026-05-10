set dotenv-load := true

default:
    @just --list

# --- Local dev ---
dev:
    docker compose --env-file .env -f deploy/docker-compose.yml up -d
    uv run python manage.py runserver 0.0.0.0:8000

worker:
    uv run celery -A config worker -l info -Q default,media,ai

beat:
    uv run celery -A config beat -l info

# --- DB ---
migrate:
    uv run python manage.py migrate

makemigrations *args:
    uv run python manage.py makemigrations {{args}}

shell:
    uv run python manage.py shell_plus || uv run python manage.py shell

# --- Tests / quality ---
test *args:
    uv run pytest {{args}}

test-cov:
    uv run pytest --cov=apps --cov-report=html --cov-report=term

lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy apps config

format:
    uv run ruff check --fix .
    uv run ruff format .

# --- Seed ---
seed:
    uv run python manage.py seed_places
    uv run python manage.py seed_events

# --- Docker ---
docker-up:
    docker compose --env-file .env -f deploy/docker-compose.yml up -d

docker-down:
    docker compose --env-file .env -f deploy/docker-compose.yml down

docker-logs:
    docker compose --env-file .env -f deploy/docker-compose.yml logs -f
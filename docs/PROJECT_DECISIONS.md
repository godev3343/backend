# Project Decisions — отклонения от исходного ТЗ

Документ ведётся вручную. Все правки ТЗ и архитектурные решения,
принятые в процессе работы — фиксируем здесь.

Последнее обновление: 2026-05-11

## Стек и инфраструктура

### Postgres image
Используем `imresamu/postgis:16-3.5-bundle0` — включает PostGIS + pgvector
+ pg_trgm + unaccent + btree_gin в одном образе. Локалка и CI на одном
и том же образе, без кастомного Dockerfile.

### Postgres credentials
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` хранятся в `.env`
(не коммитятся), пробрасываются в docker-compose через переменные.

### Pydantic-settings list-поля
`ALLOWED_HOSTS` и `CORS_ALLOWED_ORIGINS` объявлены как `str` в `AppSettings`
и парсятся хелпером `_parse_list()` — принимает CSV или JSON.
Причина: pydantic-settings парсит list-поля как JSON до запуска валидаторов,
что ломает env-файлы с CSV-форматом.

## Авторизация

### Отказались от SMS
Изначально по ТЗ Epic 2 был флоу через Mobizon SMS API. Решили вырезать:
- сложность интеграции с казахстанским провайдером
- стоимость отправки
- для Pre-MVP хватает Email + Google OAuth

`mobizon_api_key` удалён из `AppSettings`. Throttle scope `auth_sms` удалён.
SMS-флоу может вернуться в Этапе 1+ как опциональный канал.

### Email как primary identifier
`USERNAME_FIELD = "email"`. Email обязательный и уникальный.
`username` убран из модели (`AbstractBaseUser` вместо `AbstractUser`).

### Добавили email verification (не было в ТЗ)
Pre-MVP по ТЗ не требовал верификации email. Решили добавить, так как:
- email стал primary identifier
- нужен для password reset
- защита от регистрации на чужие email

Endpoints:
- `POST /api/auth/email/verify/request`
- `POST /api/auth/email/verify/confirm`

Хранение кодов: Redis, ключ `email_verify:{email}`, TTL 15 мин.

### Добавили password reset (не было в ТЗ)
Endpoints:
- `POST /api/auth/password/reset/request`
- `POST /api/auth/password/reset/confirm`

Токен: 32 байта random, Redis ключ `pwd_reset:{token}`, TTL 1 час.

### Email-провайдер: Gmail SMTP
Используем Gmail SMTP через App Password.
- Лимит: 500 писем/день
- Аккаунт: отдельный gmail для проекта (не личный)
- Settings: стандартный Django EMAIL_BACKEND, нет внешних SDK

Когда выйдем за лимит — мигрируем на Resend/SendGrid.

### IsEmailVerified
Permission применяется только к действиям, которые требуют верификации
(создание чек-инов, постов, заявок в друзья). Базовый просмотр карты
работает и для неверифицированных, чтобы не ломать UX онбординга.

## AI

### Использу​ем Gemini вместо Anthropic Claude
По ТЗ — Anthropic Claude (Haiku 4.5 + Sonnet 4.6).
На время разработки используем Gemini (бесплатный tier через AI Studio).

Архитектура `apps/ai/clients/`:
- `LLMClient` Protocol — абстракция
- `GeminiClient` — текущая реализация
- `AnthropicClient` — заглушка, подключим позже

Переключение через env `AI_PROVIDER=gemini|anthropic`.

### Модели Gemini
- `gemini-2.5-flash` (по умолчанию) — аналог Haiku, быстро, дёшево
- `gemini-2.5-pro` — аналог Sonnet, умнее

## Доменная модель

### User
Добавлены поля сверх изначального ТЗ Epic 1.1:
- `email` (unique, required, primary identifier)
- `first_name` (required)
- `last_name` (optional)
- `email_verified_at` (для email verification)
- `full_name` property (`first_name + last_name`)
- `public_name` property (`display_name or first_name`)

Убрано из ТЗ Epic 1.1:
- ничего, все поля исходного списка есть

### Friendship (без изменений от ТЗ)
Направленная: одна запись `from_user → to_user`, на accept меняем status.
`is_friends(a, b)` = OR через два направления с `status=accepted`.

### PointsTransaction (без изменений)
Идемпотентность через два partial UniqueConstraint:
- (user, reason, ref_type, ref_id) когда ref_id IS NOT NULL
- (user, reason) когда ref_id IS NULL — для одноразовых причин (signup)

Generic FK НЕ используется — обычные CharField/PositiveBigIntegerField
для ref_type/ref_id. Обратные запросы не нужны.

## Изменения, которые НЕ принимаем

(сюда пишем что обсуждали и отказались)

## История значимых решений

- 2026-05-11: вырезали SMS, добавили email-флоу с Gmail SMTP
- 2026-05-11: переключили AI на Gemini, оставили Anthropic как fallback
- 2026-05-11: добавили first_name, email обязательный
- 2026-05-11: postgres-образ → imresamu/postgis:16-3.5-bundle0
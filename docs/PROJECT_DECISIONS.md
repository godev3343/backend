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

# ============================================================
# Дописать в конец docs/PROJECT_DECISIONS.md
# Найди раздел "## История значимых решений" и допиши
# новые секции ПЕРЕД ним, а в самой истории — добавь даты.
# ============================================================


## EPIC 2 — Authorization

### JWT с rotation + blacklist
- access: 15 мин, refresh: 30 дней
- `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`
- Старый refresh после rotation попадает в blacklist через
  `rest_framework_simplejwt.token_blacklist`. Повторное использование
  украденного refresh не сработает.

### Password hashing — Argon2
В `PASSWORD_HASHERS` первым стоит `Argon2PasswordHasher`. PBKDF2 оставлен
для обратной совместимости — старые пароли работают, новые/изменённые
автоматически пересолятся в Argon2 при следующем логине.

Зависимость: `django[argon2]` в pyproject.

### User-enumeration защита
`POST /api/auth/email/verify/request` и `POST /api/auth/password/reset/request`
всегда возвращают **202 Accepted** — независимо от того, есть ли email в базе.
Это блокирует перебор существующих email через эти эндпоинты.
В тестах проверяется через `mail.outbox` — реально письмо уходит только
для существующего email.

### Google OAuth — список client_id
`GOOGLE_OAUTH_CLIENT_IDS` — CSV из env. Web, iOS, Android могут использовать
разные client_id. SDK `google.oauth2.id_token.verify_oauth2_token` принимает
только один `audience`, поэтому проверяем `aud` вручную против whitelist.

### Google linking
При логине через Google:
1. Если есть юзер с этим `google_sub` → возвращаем
2. Если есть юзер с этим email, но без `google_sub` → линкуем
   (set `google_sub`, `email_verified_at`)
3. Иначе → создаём нового, ставим `email_verified_at = now()`
   (Google уже подтвердил)

### Redis для одноразовых токенов
- Email verification: 6-значный код, TTL 15 мин, ключ `email_verify:{email}`
- Password reset: 32-байт URL-safe token, TTL 1 час, ключ `pwd_reset:{token}`
- Атомарное consume через `GETDEL` (Redis 6.2+) — против race condition
- При отсутствии `django-redis` — fallback на `GET+DELETE` (не атомарно,
  но окей для dev/test)

### Throttle scopes
- `auth_login`: 5/min (brute-force)
- `auth_register`: 5/min
- `email_verify_request`: 5/hour, ключ = email (не IP) — против перебора
  по конкретному email
- `password_reset_request`: 5/hour, ключ = email
- `google_auth`: 10/min

### Email в dev — console backend
В `config/settings/dev.py` — `console.EmailBackend` по умолчанию, чтобы
не тратить квоту Gmail на отладочные регистрации. Чтобы реально слать
через SMTP в деве — env `DJANGO_EMAIL_REAL=true`.

### Auto-clear cache в auth-тестах
`apps/users/tests/conftest.py` содержит autouse-фикстуру `_clear_cache`,
которая чистит Django cache (Redis) перед и после каждого теста. Без неё
throttle-state переживает между тестами и серия запросов на login/register
упирается в `5/min` лимит уже на 6-м запросе.

### Разделение `apps/users/` на под-пакеты
Изначально планировалось хранить весь auth в `services/auth.py`,
`serializers/auth.py`, `views/auth.py`. Решили разнести по доменам:
```
services/   — auth.py, google.py, dto.py, exceptions.py
serializers/ — register.py, tokens.py, email_verify.py, password_reset.py,
               google.py, onboarding.py
views/       — то же разбиение
```
Причина: при росте проекта в EPIC 3-6 появятся FriendshipService,
CheckInService и т.д. — каждый со своими ошибками и DTO. Иначе придётся
рефакторить позже под нагрузкой EPIC 3.

### `DomainError` — обычный Exception, не APIException
`apps/core/exceptions.py:DomainError` — это обычный `Exception` с полями
`message`, `code`, `status_code`, `errors`. **НЕ** наследник
`rest_framework.exceptions.APIException`.

Глобальный `api_exception_handler` перехватывает `DomainError` и
конвертирует в Response. Это позволяет бизнес-логике (service-слой) не
тянуть зависимость от DRF.

`AuthError(DomainError)` + все наследники (`InvalidCredentials`,
`EmailAlreadyExists`, `InvalidCode`, `InvalidResetToken`, `UserNotFound`,
`GoogleAuthError`) живут в `apps/users/services/exceptions.py`.


## EPIC 1 fixes (post-audit правки)

### Поле email_verified_at в User
Добавлено отдельной миграцией `users/0003_user_email_verified_at.py`
для нужд EPIC 2. Property `is_email_verified` возвращает
`email_verified_at is not None`.

### CheckIn.likes_count
Денормализованный счётчик на `apps/checkins/models.py`. Будет обновляться
атомарно через `F('likes_count') + 1` при like/unlike в EPIC 6.
Миграция `checkins/0002_checkin_likes_count.py`.

### Event constraint: ends_at > starts_at
`apps/events/models.py` получил второй `CheckConstraint`:
`Q(ends_at__isnull=True) | Q(ends_at__gt=F('starts_at'))`.
Миграция `events/0002_event_ends_after_starts.py`.

### Management-команды перенесены
`apps/{places,events}/commands/` → `apps/{places,events}/management/commands/`.
В первом виде Django их не находил.

### Удалён устаревший default_app_config
`apps/{users,social,places,checkins,events,gamification,feed}/__init__.py`
был с `default_app_config = "..."`. Django ≥3.2 это игнорирует, удалили.

### apps.ai в INSTALLED_APPS
До правки app существовал на диске (`apps/ai/apps.py`, `clients/`), но
не был зарегистрирован в `INSTALLED_APPS` — Django его не подхватывал.


## История значимых решений

- 2026-05-11: вырезали SMS, добавили email-флоу с Gmail SMTP
- 2026-05-11: переключили AI на Gemini, оставили Anthropic как fallback
- 2026-05-11: добавили first_name, email обязательный
- 2026-05-11: postgres-образ → imresamu/postgis:16-3.5-bundle0
- 2026-05-11: EPIC 1 fixes — email_verified_at, likes_count, Event constraint,
  перенос management-команд, удаление default_app_config, регистрация apps.ai
- 2026-05-11: EPIC 2 завершён — JWT auth, Google OAuth, email verify,
  password reset, onboarding; 55 тестов зелёные
- 2026-05-11: разделение apps/users/{services,serializers,views} на под-пакеты
- 2026-05-11: DomainError остался Exception (не APIException), AuthError
  наследуется от него
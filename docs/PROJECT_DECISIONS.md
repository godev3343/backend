# Project Decisions

Архитектурные решения и отклонения от исходного ТЗ. Документ ведётся вручную.

## Стек и инфраструктура

**Postgres image:** `imresamu/postgis:16-3.5-bundle0` — PostGIS + pgvector + pg_trgm + unaccent + btree_gin в одном образе. Локалка и CI на одном образе.

**Pydantic-settings list-поля:** `ALLOWED_HOSTS` и `CORS_ALLOWED_ORIGINS` объявлены как `str` и парсятся хелпером `_parse_list()` (CSV или JSON). Иначе pydantic-settings парсит list-поля как JSON до запуска валидаторов и ломает CSV-формат.

**Email-провайдер:** Gmail SMTP через App Password, лимит 500 писем/день. Отдельный gmail для проекта. В dev — `console.EmailBackend` по умолчанию, реальная отправка через `DJANGO_EMAIL_REAL=true`.

**AI-провайдер:** Gemini вместо Anthropic Claude из ТЗ (бесплатный tier через AI Studio). Архитектура `apps/ai/clients/` через `LLMClient` Protocol, переключение через `AI_PROVIDER=gemini|anthropic`. Модели: `gemini-2.5-flash` (рутина), `gemini-2.5-pro` (сложное). Anthropic-клиент — заглушка.

## Авторизация

**SMS-флоу вырезан.** Изначальный Epic 2 предполагал Mobizon SMS. Отказались: стоимость, сложность интеграции с казахстанским провайдером, для Pre-MVP хватает Email + Google. `mobizon_api_key` удалён, throttle scope `auth_sms` удалён. Может вернуться в Этапе 1+ как опциональный канал.

**Email как primary identifier.** `USERNAME_FIELD = "email"`, `AbstractBaseUser` вместо `AbstractUser` (убрали `username`). Email обязательный, уникальный.

**Email verification + password reset добавлены сверх ТЗ.** Email стал primary identifier, нужна верификация для password reset и защиты от регистрации на чужие. Endpoints `/api/auth/email/verify/{request,confirm}` и `/api/auth/password/reset/{request,confirm}`. Токены в Redis: код 6 цифр для email (TTL 15 мин), 32-байт URL-safe для reset (TTL 1 час). Atomic consume через `GETDEL` (Redis 6.2+).

**`IsEmailVerified` permission** применяется только к действиям, требующим доверия (чек-ины, заявки в друзья), не блокирует базовый просмотр карты и онбординг.

**JWT с rotation + blacklist.** access 15 мин, refresh 30 дней. `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True` через `token_blacklist` app — украденный refresh после rotation не сработает.

**Password hashing — Argon2 первым.** В `PASSWORD_HASHERS` Argon2 + PBKDF2 для обратной совместимости. Зависимость `django[argon2]`.

**User-enumeration защита.** `email/verify/request` и `password/reset/request` всегда возвращают 202, независимо от существования email. В тестах проверка через `mail.outbox`.

**Google OAuth — whitelist client_id.** `GOOGLE_OAUTH_CLIENT_IDS` — CSV из env (web/iOS/Android могут иметь разные). `aud` проверяется вручную против whitelist. Linking: по `google_sub` → по email → создание нового с `email_verified_at=now()`. `profile.picture` игнорируется — внешний URL без EXIF-strip/WebP-конверсии не вписывается в инвариант "все картинки через MediaAsset".

**Throttle scopes:** `auth_login` 5/min, `auth_register` 5/min, `email_verify_request` 5/hour (ключ = email), `password_reset_request` 5/hour (ключ = email), `google_auth` 10/min.

**Auto-clear cache в auth-тестах** через autouse-фикстуру в `apps/users/tests/conftest.py`. Без неё throttle-state переживает между тестами.

## Доменная модель

**User поля сверх ТЗ:** `email`, `first_name` (required), `last_name`, `email_verified_at`, `full_name` property, `public_name` property, `preferred_vibes` (ArrayField), `ai_context` (CharField 500).

**`User.preferred_vibes` — ArrayField, не M2M.** Короткий список фиксированных значений (≤5 строк × 20 байт). M2M-таблица дала бы лишний JOIN на каждый запрос профиля. Валидация значений в сериализаторе, не БД-constraint (PG не enforces choices на массивах без custom check).

**`User.avatar_url` — property через `avatar_asset.url_feed`.** Поле было удалено в EPIC 4, но read-код продолжал к нему обращаться. Write-стороны (PATCH /me, onboarding, Google) больше не принимают/не сохраняют — аватары только через /api/upload/*.

**`Place.city` — CharField с choices, не отдельная таблица.** На pre-MVP только Астана, список меняется редко, JOIN ничего не выигрывает. Дефолт `astana`.

**`Friendship` — направленная, одна запись на пару.** На accept меняем status, не создаём зеркальную. `is_friends(a,b)` = OR через два направления с `status=accepted`.

**`PointsTransaction` идемпотентность** через два partial UniqueConstraint: `(user, reason, ref_type, ref_id)` когда ref_id NOT NULL, `(user, reason)` когда NULL. Generic FK не используем — обычные CharField/PositiveBigIntegerField.

**`MediaAsset` — single source of truth.** PlacePhoto и User.avatar_asset ссылаются через FK. Поля r2_key_*/width/height не дублируются. App label `media_app` (default `media` конфликтует со встроенным Django).

**`CheckIn.photo → PlacePhoto`** (не на MediaAsset напрямую). Фото из чек-ина автоматически попадает в галерею места — естественный shared resource. PlacePhoto на asset реюзается при retry с тем же `photo_key`.

**`CheckIn.likes_count` денормализован.** Обновляется через F-выражение в `LikeService`, не через сигнал. F-выражение атомарно, защита от гонок. Decrement через `Greatest(F-1, 0)` — не уходит в минус при рассинхронизации.

**`Event.location` денормализован из `Place.location`.** Копируется в `Event.save()`. `/api/events?bbox=...` фильтрует по одному GIST-индексу без JOIN. Инвариант: при наличии place координаты = place.location. Если Place перемещается в админке — связанные события автоматически НЕ обновляются (явная зона ответственности админа на pre-MVP).

## Ошибки и сервис-слой

**`DomainError` — обычный Exception, не APIException.** Поля `message`, `code`, `status_code`, `errors`. Глобальный `api_exception_handler` перехватывает и конвертирует в Response. Бизнес-логика (service-слой) не тянет зависимость от DRF.

**Структура `apps/users/`:** services/serializers/views разнесены по поддоменам (auth, google, email_verify, password_reset, onboarding, register, tokens). Это масштабируется на остальные app без переделки при росте.

**Exception handler с Sentry capture.** Для unhandled exception (когда DRF `exception_handler` вернул None) пишем `sentry_sdk.capture_exception` с `push_scope` + user_id. `push_scope` изолирует scope per-request (критично в sync gunicorn workers). Sentry sample_rates=0 на pre-MVP — free tier 5k events/мес.

## API и URLs

**Permissions:** `/api/places` и `/api/events` — AllowAny (карта первая поверхность, должна быть видна до регистрации). Геокодинг — IsAuthenticated (платный апстрим). `/api/ai/recommend` — IsAuthenticated + IsOnboarded.

**OpenAPI auto-tags по `app_label`.** Preprocessing hook (`apps/core/openapi.py`) проставляет тег по `view.__module__` (`apps.users.*` → `users`). Path-override для `/api/auth/*` → `auth`. Новый app автоматом получает тег по имени, без обвешивания views декораторами. Полная документация request/response отложена.

**CsrfViewMiddleware восстановлен** в MIDDLEWARE для админки. На API noop — там JWT, нет SessionAuthentication. `CORS_ALLOW_CREDENTIALS=False` явно. `CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS`.

**`/api/feed` живёт в apps.checkins, не в apps.feed.** `apps.feed` зарезервирован, пустой. Лента — проекция чек-инов. Свои чек-ины из ленты исключены (есть `/me`), при необходимости — `include_self=true` query-param.

**`GET /api/users/me/points` в apps.gamification.** Path сохраняется через префикс в `apps.gamification.urls`. Альтернатива (view в apps.users) тянула бы импорт PointsTransaction в users.

**`PATCH /api/users/me` и `PUT /api/users/me/preferences` — два эндпоинта.** Семантика разная: PATCH — частичный апдейт профиля как целого; PUT — атомарная замена AI-настроек (идемпотентно для онбординг-retry).

## Подсчёт и геопространство

**Дистанция через `ST_DWithin(geography, geography, 100)`.** Реализация через `.extra(where=...)`. Cast в `geography` обязателен — на `geometry` SRID=4326 расстояние в градусах. Geography даёт метры с учётом сферичности.

**Кэш через версионирование, не `delete_pattern`.** Встроенный Django RedisCache не поддерживает `delete_pattern`. Ключ `places:list:v{N}:...`, на save/delete `cache.incr('places:version')` — O(1), без сканирования. TTL 60s зачищает старые. Та же схема для AI-context-кэша (ключ `ai:vibes_version`).

**BBox округляется до 3 знаков в cache key** (~110м). Без этого панорамирование на 10м даёт cache miss из-за float-precision.

**`MAX_BBOX_SPAN_DEG = 2.0`** (≈220км). Запрос с большей диагональю — 400 `bbox_too_large`. Защита от DoS.

**`primary_vibe` через Subquery** в list-queryset. Без этого N+1 либо prefetch+Python-постфильтр. Сортировка маркеров через boolean `ExpressionWrapper(Q(...), BooleanField())` — у мест с фото и вайбом приоритет.

**Мульти-vibe — OR semantics** (`?vibe=calm,romantic`). AND был бы слишком узкой выдачей.

**`thumb_url` только PROCESSED-ассеты.** Иначе на маркер прилетел бы оригинал (мог быть HEIC).

**recent_checkins — отдельный запрос, не `Prefetch` со slice.** Prefetch со срезом применяет лимит к JOIN'у для всего набора, не per-place. На single-get случайно работает, паттерн опасный.

## Геокодинг (apps.geocoding)

**Отдельное app, не часть places.** На этапе 2 заменим Mapbox на Photon. Изоляция упрощает миграцию.

**Mapbox v6 free tier (100k/мес), forward only.** Прокси через бэк (не клиентский SDK) — токен не утекает в мобильные, throttle на нашей стороне, кэш Redis 24ч экономит квоту, миграция на Photon без релизов клиентов.

**Cache key — `md5(normalized_query)` + локаль + страна, proximity не включён.** Запрос "Кафе" из Астаны и из Алматы вернёт разные топовые, но для текущего use-case (поиск адреса админом) хватает.

**Country=kz по умолчанию.**

## Медиа и R2

**Avatar replacement через post_save сигнал.** При `MediaAsset` PENDING→PROCESSED обновляем `User.avatar_asset` и удаляем старый из БД и R2. В сигнале, а не в task — task не знает про User.

**WebP конверсия условная для original.** ≤2048px по длинной стороне — оригинал в исходном формате. Иначе перезаписывается в WebP, старый ключ удаляется. Feed/thumb — всегда WebP (quality 85/80).

**Min short side 400px** — иначе `failure_reason=TOO_SMALL`.

**`transaction.on_commit` в тестах** требует `@pytest.mark.django_db(transaction=True)` — без этого callbacks не вызываются в pytest-django.

## Чек-ины и лента

**Like — идемпотентный API.** POST × N → один Like, повторный = 200. DELETE без предыдущего лайка = 200, не 404. Естественное поведение для тапа на сердечко; 409/404 ломали бы UI при race.

**FIRST_CHECKIN — личная семантика, не социальная.** В декомпозиции 6.1 была неоднозначность ("первый среди друзей"). Привели к бизнес-плану §5.1: личный бонус за разведку, `EXISTS(CheckIn user=user, place=place)` до создания. Проще запрос, проще тесты. Социальный бонус "первый среди друзей" — отложен.

**Cursor-pagination для /me и /feed** через `('-created_at', '-id')`. Tiebreak по id обязателен (одинаковый timestamp при batch-импорте). Не offset — на ленте друзей offset → DoS-вектор.

## AI

**Structured output через Gemini JSON mode**, не текстовый парсинг. `response_mime_type=application/json` + `response_schema`. Когда подключим Anthropic — аналог через tool_use, контракт `LLMClient` не меняется.

**Hallucinated place_id — белый список.** `build_context()` возвращает `frozenset[int]` со всеми id в контексте. Post-filter по списку, пусто → 502 `ai_no_valid_places`.

**`name` мест из БД, не из ответа модели.** Даже при верном id модель могла обрезать/перевести.

**`AiRequestLog` — всегда пишется,** успех и ошибки. Критично для дебага и контроля биллинга (платим за input даже при невалидном ответе). `response_summary` = id + reasoning, не полный ответ.

**Async-сервис, sync-view через `async_to_sync`.** LLM-вызов 1-5 сек, async-стек обработает много параллельных запросов без блокировки. DRF view остаётся sync — миграция на ASGI не оправдана пока эндпоинт не горячий.

## Friendship

**Decline = hard delete** (не `status=declined`). Проще логика, можно повторно отправить заявку без retry-механизма поверх unique-constraint. Минус: нет истории отклонённых.

**Counter-pending auto-accept в `send_request`.** Если b → a pending и a отправляет заявку b — авто-accepted. Устраняет race двойного pending когда оба добавили друг друга одновременно. Альтернатива (409 и заставить второго принять входящую) хуже для UX.

**`cancel_request` — отдельный эндпоинт** (DELETE /api/friends/requests/{id}). Без него фронт не может убрать отправленную заявку.

## Геймификация

**`POINTS_BY_REASON` приведён в соответствие с бизнес-планом §5.1.** Оставлено только то что реально вызывается:
- `CHECKIN: 5` — каждый чек-ин
- `FIRST_CHECKIN: 10` — первый чек-ин юзера в этом месте
- `FRIEND_ADDED: 5` — обоим юзерам на accept

SIGNUP/REFERRAL вырезаны как мёртвые крючки. REFERRAL вернётся в Этапе 1 с полной инфраструктурой (referral_code, антифрод, deep-link).

**FRIEND_ADDED — без anti-abuse, `ref_id=friendship.pk`.** Decline + новый accept = новый friendship = новое начисление. Сознательная плата за простоту: магазина наград нет, leaderboard нет, сезонное обнуление в Этапе 1 всё равно сбросит. Антифрод — Этап 1.

**Начисление в обеих ветках accept:** `accept_request` и counter-pending auto-accept в `send_request`.

## Сидинг

**`seed_places` — один скрипт для дев-фикстур и production.** Приоритет города: `places[].city` > `meta.city` > `--city` параметр > дефолт `astana`. Идемпотентность через `update_or_create` по `name` + пересоздание вайбов на каждый запуск. `fixtures/places_astana.json` — 50 заведений с ручной вайб-разметкой; на Этапе 1 разметка станет автоматической (Celery Beat + LLM).

## Кросс-функциональное

**E2E happy-path в одном файле** `tests/test_e2e_flow.py`. Ловит регрессии межапп-взаимодействия. Юнит-тесты — рядом с кодом в `apps/*/tests/`. LLM/R2/Mapbox в тестах замоканы, реальные вызовы запрещены.

## Отложено в Этап 1

- SMS-флоу (Mobizon или альтернатива)
- Реферальная система (`REFERRAL` reason + referral_code/referred_by/deep-link)
- Антифрод для FRIEND_ADDED (`ref_type='friendship_pair'` или таблица истории)
- Сезонное обнуление поинтов
- Auto-update Event.location при перемещении Place
- Anthropic Claude как production-провайдер AI (сейчас заглушка)
- Vibe-разметка автоматическая (Celery Beat + LLM на отзывах)
- proximity-aware cache для геокодинга
- Полная документация OpenAPI request/response (сейчас только auto-tags + JWT button)
- Социальный FIRST_CHECKIN ("первый среди друзей") как отдельный reason
- Замена Mapbox на собственный Photon
- B2B-кабинет с server-side upload событий (сейчас cover_url через админку)
- Migration на ASGI когда `/api/ai/recommend` станет горячим
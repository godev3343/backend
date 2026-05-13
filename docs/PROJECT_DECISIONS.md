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


## EPIC 3 — Профиль и друзья

### Decline = hard delete
В декомпозиции EPIC 3.6 не уточнено поведение decline. Выбрали hard delete
вместо `status=declined`:
- Проще логика (нет специального статуса).
- Можно повторно отправить заявку после decline без retry-механизма
  поверх unique-constraint.
- Нет накопления мусорных строк со временем.
Минус: нет истории отклонённых заявок (если понадобится для антиспама —
вернёмся к статусу `declined`).

### Counter-pending auto-accept в send_request
Если b → a уже pending, и a отправляет заявку b — автоматически становится
accepted (одна запись b → a, status=accepted). Устраняет race-сценарий
двойного pending, когда оба добавили друг друга одновременно.

В декомпозиции этого не было; стандартная альтернатива — отдавать 409
"friendship_exists" и заставлять второго юзера найти входящую и принять.
Решили в пользу UX.

### cancel_request — отдельный эндпоинт
DELETE /api/friends/requests/{id} — отмена своей исходящей заявки.
В декомпозиции его не было, но без него фронт не может убрать отправленную
заявку. Permission: только from_user.

### Поинты за accept — отложено до EPIC 9
TODO-хуки оставлены в FriendshipService.accept_request и в
counter-pending-ветке send_request. PointsService.award вызовем в EPIC 9
вместе с остальной геймификацией.

### История значимых решений
- 2026-05-11: EPIC 3 завершён — профиль, поиск, friendship-флоу;
  counter-pending auto-accept, decline = hard delete, cancel_request
  добавлен сверх ТЗ

## EPIC 4 — Медиа и R2 (закрыт 2026-05-11)

### Single source of truth — MediaAsset
PlacePhoto и User.avatar_asset ссылаются на MediaAsset через FK.
В PlacePhoto и User не дублируются поля r2_key_*/width/height.

### App label media_app
`apps/media/apps.py` определяет `label = "media_app"` — default `media`
конфликтует со встроенным Django.
Таблица `media_asset` (явно через Meta.db_table).
FK на MediaAsset идут через прямой импорт класса, не lazy-string —
иначе `auth.checks.check_user_model` падает на инстанцировании User().

### Avatar replacement через post_save сигнал
При processing аватара (status: PENDING→PROCESSED) signals.py:
1. Записывает new asset в User.avatar_asset
2. Удаляет старый MediaAsset из БД и его файлы из R2 (bulk delete)

Альтернатива — делать это в task. Сигнал выбран чтобы task не знал про User
и не зависел от User-модели.

### WebP конверсия — условная для original
Если оригинал ≤ 2048px по длинной стороне — остаётся в исходном формате.
Если был downscale — перезаписывается в WebP, старый ключ удаляется.
Feed/thumb — всегда WebP (quality 85/80).

### Min short side = 400px
Меньше → MediaAsset.failure_reason=TOO_SMALL.

### Тесты с transaction.on_commit
Используется @pytest.mark.django_db(transaction=True) только в test_signals.py.
Без этого on_commit callbacks не вызываются в pytest-django.

## EPIC 5 — Карта и заведения

### Permissions: AllowAny на /api/places и /api/places/{id}
По ТЗ 2.2.4 карта — первая поверхность, которую видит юзер. Чтобы онбординг
не превращался в "сначала зарегайся, потом смотри что у нас есть", read-доступ
открыт всем. Запись через эти эндпоинты невозможна — только админка.

### List отдаёт только is_verified=True
В list-выдаче — только верифицированные места. Detail возвращает место по id
независимо от is_verified (полезно для админских ссылок на пре-модерируемый
контент). Если потом захотим прятать и detail — добавим фильтр в `build_detail_queryset`.

### Кэш через версионирование, не delete_pattern
Встроенный `django.core.cache.backends.redis.RedisCache` НЕ поддерживает
`delete_pattern` — это метод django-redis. Чтобы не плодить зависимость,
сделали версионируемый кэш: `places:version` (INCR в Redis) встроен в ключ
`places:list:v{N}:...`. Любое save/delete Place/PlaceVibe/PlacePhoto делает
`cache.incr('places:version')` — O(1), без сканирования ключей. Старые ключи
протухают по TTL=60s.

### BBox округляется до 3 знаков в cache key
~110м точность. Без этого панорамирование карты на 10м каждый раз даёт
cache miss из-за float-precision в bbox от клиента.

### MAX_BBOX_SPAN_DEG = 2.0
Запросы с диагональю больше 2° (≈220км) возвращают 400 `bbox_too_large`.
Защита от DoS и от случайного запроса "верни мне всю Землю".

### primary_vibe считается через Subquery
В list-queryset аннотируется через `Subquery(PlaceVibe.objects.filter(place=OuterRef).order_by(-weight).values('tag')[:1])`.
Без этого был бы N+1 (либо prefetch+Python-постфильтр на каждом маркере).

### Мульти-vibe — OR semantics
`?vibe=calm,romantic` возвращает места хотя бы с одним из вайбов. AND был бы
слишком узкой выдачей (мало мест имеют 3+ сильных вайба).

### thumb_url только PROCESSED-ассеты
Если у места только pending-фото, `thumb_url=null` в list. Иначе на маркер
прилетел бы оригинал (мог быть HEIC, который не открывается в браузере).

### thumb-ассеты подгружаются вторым запросом
В build_list_queryset аннотируется только `thumb_asset_id`. URL'ы для них
загружаются одним батч-запросом по `id__in=[...]` в view. Альтернатива —
JOIN на MediaAsset в основном queryset — увеличила бы payload по wire
для типового случая, где много мест без фото.

### Sorting в list через boolean ExpressionWrapper
`order_by(Q(...))` запрещён в Django 5 (`Q` не имеет `.asc()`). Используем
boolean-аннотации `_has_photo` / `_has_vibe` через `ExpressionWrapper(Q(...),
BooleanField())` и сортируем по ним desc — у мест с фото и вайбом приоритет
на карте.

### recent_checkins — отдельный запрос, не Prefetch со slice
`Prefetch('checkins', queryset=qs[:5])` применяет лимит к JOIN'у для всего
набора, не per-place. На detail с одним местом случайно работает, но паттерн
опасный — заменили на явный `CheckIn.objects.filter(place=place)[:N]`.

### Signal на PlacePhoto тоже инвалидирует кэш
Не только Place/PlaceVibe, но и PlacePhoto — потому что thumb_url попадает
в list-payload.


## EPIC 5 — Геокодинг (apps.geocoding)

### Отдельное app
Не часть apps.places. Геокодинг живёт своей жизнью: на этапе 2 заменим
Mapbox на собственный Photon. Когда логика провайдера в отдельном app —
миграция трогает только его, не сериализаторы Place.

### Mapbox Geocoding API v6, free tier
До 100k запросов в месяц бесплатно. Перенос на Photon — этап 2 (см. ТЗ 1.3).
Endpoint `forward` (текст → координаты), `reverse` пока не нужен.

### Прокси через бэк, не клиентский SDK
По принципу ТЗ 1.4 "проксирование запросов через свой бэкенд":
- Mapbox-токен не утекает в мобильные клиенты (referer-restriction на mobile не работает).
- Throttle на нашей стороне (`geocode: 60/hour` per user).
- Кэш Redis 24ч — экономит квоту.
- Миграция на Photon — без релизов клиентов.

### Permissions: IsAuthenticated
Не AllowAny. Геокодинг проксирует платный апстрим — открывать анонимам
приглашает к сжиганию квоты. Карта остаётся открытой (AllowAny на /api/places),
а геокодинг — авторизованным.

### Cache key — md5(normalized_query)
Запрос приводится к lower + strip + collapse-whitespace, затем хэшируется
в md5 (не для безопасности, для компактного детерминированного Redis-ключа).
В ключ включена локаль и страна, чтобы один и тот же текст для ru/kk не
конфликтовал.

### Proximity НЕ участвует в cache key
Запрос "Кафе" из Астаны и из Алматы вернёт разные топовые результаты, но для
текущего use-case (поиск конкретного адреса админом) этого хватает. Если
позже понадобится proximity-aware cache — добавим в ключ.

### Country=kz по умолчанию
Mapbox `country=kz` ограничивает выдачу Казахстаном — мы сейчас работаем
только по KZ. Клиент может переопределить query-параметром `country`.

## EPIC 6 — Чек-ины и лента
 
### Дистанция через PostGIS на geography-cast
`CheckInService._check_distance` использует `.extra(where=[...])` с условием:
```sql
ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 100)
```
Cast в `geography` обязателен. На `geometry` с SRID=4326 расстояние
интерпретируется в **градусах**, не метрах — `ST_DWithin(..., 100)` без cast
вернёт всё в радиусе ~11 000 км. Geography-cast даёт расстояние в метрах
с учётом сферичности Земли.
 
Альтернативы которые отвергли:
- ORM-lookup `location__distance_lte` — работает в градусах для SRID=4326.
- Geodjango `Distance(geog)` функция — она в SELECT, не в WHERE; для одной
  exists-проверки overkill.
- Считать расстояние в Python (haversine) — точно, но требует загружать
  геометрию места в process; на масштабе слабее и менее тестируемо.
### Семантика бонуса FIRST_CHECKIN
ТЗ 6.1: "первый чек-ин среди друзей пользователя в этом месте".
Уточнили (потому что в ТЗ неоднозначно):
- Если у юзера 0 друзей → бонуса нет (это **social** бонус).
- Включаем самого юзера в проверку "никто ещё не был" — иначе повторные
  чек-ины крутят бонус.
Реализация: один SQL с EXISTS, без выгрузки списка друзей в Python.
См. `CheckInService._is_first_checkin_among_friends`.
 
### `CheckIn.photo` ссылается на `PlacePhoto`, не на `MediaAsset` напрямую
Текущая модель (с EPIC 1) уже была такой; мы её не меняли.
 
Флоу при `photo_key` в POST /api/checkins:
1. Находим `MediaAsset(key_original=photo_key, owner=user, purpose=CHECKIN, status=PROCESSED)`.
2. Если на этот asset уже есть `PlacePhoto` (OneToOne) — переиспользуем
   (покрывает retry с тем же photo_key).
3. Иначе создаём новую `PlacePhoto(place, asset, uploaded_by=user)`.
Следствие: фото чек-ина автоматически попадает и в галерею места.
Это естественный shared resource — мы не моделируем отдельно
"фото чек-ина" и "фото места", они одно и то же.
 
Альтернативы которые отвергли:
- `CheckIn.photo → MediaAsset` напрямую: чище (фото чек-ина — приватный
  ресурс), но требует миграции модели и теряет преимущество "фото чек-ина
  в карточке места".
### `Like` — простая модель, без сигналов на счётчик
`CheckIn.likes_count` обновляется в `LikeService` через F-выражение, не через
post_save сигнал. Причины:
- Сигналы — две точки начисления, сложнее тестировать.
- F-выражение атомарно на стороне БД, защищает от гонок.
- Decrement защищён `Greatest(F('likes_count') - 1, 0)` — даже при
  рассинхронизации счётчик не уходит в минус.
### Like — идемпотентный API
- POST /like × N → один Like, счётчик +1. Повторный POST = 200, не 409.
- DELETE /like без предыдущего лайка → 200, не 404.
Это естественное поведение для тапа на сердечко. 409/404 ломали бы UI
при race conditions (двойной тап, флакающий нет).
 
### `PointsService` появляется в EPIC 6, а не в EPIC 9
В декомпозиции PointsService формально в EPIC 9. Но EPIC 6 уже требует
начисление поинтов за чек-ины. Решили реализовать сервис сейчас (минимально
работающий: award + идемпотентность через savepoint + F-инкремент юзера),
в EPIC 9 добавим endpoint истории и расширим reasons.
 
`POINTS_BY_REASON` — единый источник правды по размеру награды,
не хардкод чисел в вызывающих сервисах.
 
### Cursor-pagination для /me и /feed
`CheckInCursorPagination` с ordering `('-created_at', '-id')`.
Tiebreak по id обязателен — без него курсор может пропустить/повторить
записи с одинаковым timestamp (бывает при массовом seed'е или
batch-импорте).
 
Не offset: на ленте друзей offset → потенциальный DoS-вектор
(`OFFSET 1000` сканирует 1000 строк впустую).
 
### `/api/feed` живёт в apps.checkins, не в apps.feed
В `INSTALLED_APPS` `apps.feed` зарезервирован, но пустой. Лента — это
де-факто проекция чек-инов, и весь код (модели CheckIn, Like, сериализаторы,
сервис) уже в `apps.checkins`. Плодить второй app на один эндпоинт —
overhead без выигрыша. Если позже появится "лента событий" / "лента
рекомендаций" — переедем.
 
### `/api/feed` исключает свои чек-ины
Свои — через `/api/checkins/me`. Если потом захотим смешанную ленту
"я + друзья" — добавим query-param `include_self=true`.
 
# ============================================================
# В "## История значимых решений" добавить:
# ============================================================
- 2026-05-12: EPIC 6 завершён — чек-ины, лента, лайки, PointsService;
  семантика FIRST_CHECKIN уточнена (нужны друзья, юзер включён в "уже был")
## EPIC 7 — События

### Денормализация `Event.location` из `Place.location`
`Event.save()` копирует `place.location` в `event.location`, если событие
привязано к Place. Миграция `events/0003_event_backfill_location.py`
проставляет это для существующих ивентов.

Зачем: `/api/events?bbox=...` фильтрует по одному GIST-индексу на
`event.location` без JOIN на `places`. Альтернатива через COALESCE/JOIN
работает, но усложняет план запроса и не даёт использовать индекс.

Инвариант: если у события задан `place` — `event.location === place.location`,
кастомный location перезаписывается. Кастомный location актуален только
при `place=None`. Если `Place.location` поменяется в админке — связанные
ивенты НЕ обновятся автоматически (на pre-MVP это явная зона ответственности
админа; в Этапе 1 если будет нужно — добавим post_save сигнал на Place).

### Семантика окна "событие активно в [from, to)"
`starts_at < to AND (ends_at > from OR (ends_at IS NULL AND starts_at >= from))`.

Это включает: одноразовые ивенты в будущем (нет ends_at, starts_at в окне),
длящиеся (ends_at > from), и исключает закончившиеся. Прошедшие одноразовые
(`starts_at < now, ends_at IS NULL`) исключаются автоматически при дефолтном
`from = now`.

`/api/events/{id}` не фильтрует по периоду — карточка доступна по прямой
ссылке даже для прошедших событий.

### Permissions: AllowAny
По аналогии с EPIC 5. Афиша — это публичный контент, до регистрации
должна быть видна для онбординга.

### `cover_url` остался `URLField`, не MediaAsset
Для pre-MVP события (~10 шт) добавляются админом вручную, картинка
загружается в R2 через S3-клиент и URL копируется в форму. Перевод
на MediaAsset с server-side upload в админке отложен до Этапа 1, когда
B2B-кабинет начнёт создавать события с фронта.

### bbox-парсинг продублирован, не вынесен в core
30 строк в `apps/events/filters.py` — копия из `apps/places/filters.py`.
Cross-app импорт `PlacesError` в events создал бы скрытую зависимость
между несвязанными доменами. Если появится третий эндпоинт с bbox-фильтром
(скорее всего AI-recommend в EPIC 8 — нет, там без bbox) — вынесем в
`apps/core/geo.py`.

### История значимых решений
- 2026-05-12: EPIC 7 завершён — афиша, карточка, bbox-фильтр через
  денормализованный `Event.location`, period-фильтр с семантикой
  активного окна.

### 2026-05-12: дочистка `User.avatar_url`
Поле было удалено в EPIC 4 (миграция `users/0005_remove_user_avatar_url_user_avatar_asset`),
но три места продолжали к нему обращаться:
- `apps/social/serializers/{friendship,user_public,user_me}.py` — URLField без backing-атрибута
- `apps/users/services/google.py` — передавал `avatar_url=profile.picture` в `create_user`
- `apps/users/views/onboarding.py` — `user.save(update_fields=[..., 'avatar_url'])`

Решение: добавили `@property User.avatar_url -> str | None` через `avatar_asset.url_feed`.
Read-код продолжает работать без изменений. Write-стороны (PATCH /me,
POST /onboarding, Google OAuth create) больше не принимают/не сохраняют
`avatar_url` — аватары грузятся только через /api/upload/* флоу из EPIC 4.

`profile.picture` от Google игнорируется: внешний URL без EXIF-strip и
WebP-конверсии не вписывается в инвариант "все картинки — через MediaAsset".

# Дописать в конец docs/PROJECT_DECISIONS.md ПЕРЕД секцией
# "## История значимых решений":

## EPIC 8 prep — миграции и сидинг

### `Place.city` — CharField с choices, не отдельная таблица
На pre-MVP только Астана. Список городов меняется редко, JOIN на таблицу
Cities ничего не выигрывает. CharField с `choices=City.choices` + db_index —
индекс работает, ORM-чек на стороне Python, choices видны в админке.

Дефолт `astana`. Существующие места после миграции остаются с дефолтом —
это корректно, т.к. на момент миграции в БД только Астана.

### `User.preferred_vibes` — ArrayField, не M2M-таблица
Это всегда короткий список из фиксированных значений (≤ 5 строк по 20 байт).
M2M-таблица UserVibePreference дала бы лишний JOIN на каждый запрос профиля.
ArrayField с PG-native типом — один column, один read.

Валидация значений — на уровне сериализатора (см. `apps/social/serializers/
preferences_validation.py`), не constraint в БД, т.к. PG не enforces choices
на массивах без custom check constraint.

### `PATCH /api/users/me` и `PUT /api/users/me/preferences` — два эндпоинта
Сознательное дублирование функциональности (оба пишут в одни и те же два поля),
но семантика разная:
- `PATCH /me` — частичный апдейт профиля как целого. Юзер редактирует "О себе"
  и заодно поправил вайбы.
- `PUT /preferences` — атомарная замена AI-настроек. Идемпотентно. Используется
  в онбординг-флоу (фронт может повторить PUT при retry без побочных эффектов).

Альтернатива (только PATCH /me) делала бы UX онбординга хуже: фронт обязан
знать какие именно поля присылать, а PATCH с пустым `preferred_vibes` неоднозначен
(`[]` = "очистить" vs "не трогать").

### Сидер `seed_places` — расширен под `--city` и `meta.city` в фикстуре
Один и тот же скрипт для дев-фикстур и для production-сида Астаны. Приоритет
города: `places[].city` > `meta.city` > `--city` параметр > дефолт `astana`.
Идемпотентность через `update_or_create` по `name` + удаление и пересоздание
вайбов на каждый запуск.

В фикстуре `fixtures/places_astana.json` — 50 реальных заведений с описаниями,
координатами и вайб-разметкой вручную. На Этапе 1 vibe-разметка станет
автоматической (Celery Beat + LLM), описания — из реальных отзывов.

# В "## История значимых решений" допиши:
- 2026-05-13: EPIC 8 prep — Place.city (default astana), User.preferred_vibes
  + ai_context, PUT /api/users/me/preferences, seed_places расширен под --city,
  fixtures/places_astana.json (50 мест)
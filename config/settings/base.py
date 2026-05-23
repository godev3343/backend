"""Base settings — общие для всех окружений."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from drf_spectacular.plumbing import get_lib_doc_excludes as _default_lib_doc_excludes
from corsheaders.defaults import default_headers


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CORS_ALLOW_HEADERS = (*default_headers, "x-retry")


class AppSettings(BaseSettings):
    """Типизированные env-переменные. Падаем на старте если что-то не так."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core
    secret_key: str = Field(min_length=32)
    debug: bool = False
    allowed_hosts: str = "*"

    # Database / Redis
    database_url: str
    redis_url: str

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket: str = ""
    r2_endpoint_url: str = ""
    r2_public_url: str = ""

    # Media uploads
    upload_max_size_avatar: int = 5 * 1024 * 1024
    upload_max_size_checkin: int = 20 * 1024 * 1024
    upload_max_size_place: int = 20 * 1024 * 1024
    upload_max_size_review: int = 20 * 1024 * 1024
    upload_presign_ttl: int = 300
    media_min_short_side: int = 400

    # AI
    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    # Google OAuth — список client_id через CSV (web + ios + android могут различаться)
    google_oauth_client_ids: str = ""

    # Email (Gmail SMTP по умолчанию)
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_host_user: str = ""
    email_host_password: str = ""
    email_use_tls: bool = True
    default_from_email: str = "AI Reality Map <projectgodev22315@gmail.com>"

    # Frontend (для ссылок в письмах)
    frontend_url: str = "http://localhost:3000"

    # Sentry
    sentry_dsn: str = ""
    environment: str = "dev"

    # CORS
    cors_allowed_origins: str = ""


def _parse_list(raw: str) -> list[str]:
    """Превращает строку env в list[str]. Принимает CSV или JSON."""
    import json

    s = (raw or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in s.split(",") if item.strip()]


env = AppSettings()  # type: ignore[call-arg]

# ---------- Cloudflare R2 / Media ----------------------------------------

R2_ACCOUNT_ID = env.r2_account_id
R2_ACCESS_KEY = env.r2_access_key
R2_SECRET_KEY = env.r2_secret_key
R2_BUCKET = env.r2_bucket
R2_ENDPOINT_URL = env.r2_endpoint_url
R2_PUBLIC_URL = env.r2_public_url.rstrip("/")

UPLOAD_MAX_SIZE: dict[str, int] = {
    "avatar": env.upload_max_size_avatar,
    "checkin": env.upload_max_size_checkin,
    "place": env.upload_max_size_place,
    "review": env.upload_max_size_review,
}
UPLOAD_PRESIGN_TTL = env.upload_presign_ttl
MEDIA_MIN_SHORT_SIDE = env.media_min_short_side

# ---------- AI -----------------------------------------------------------

AI_PROVIDER = env.ai_provider
GEMINI_API_KEY = env.gemini_api_key
GEMINI_MODEL = env.gemini_model
ANTHROPIC_API_KEY = env.anthropic_api_key
ANTHROPIC_MODEL = env.anthropic_model

# ---------- Google OAuth -------------------------------------------------

GOOGLE_OAUTH_CLIENT_IDS = _parse_list(env.google_oauth_client_ids)

# ---------- Frontend -----------------------------------------------------

FRONTEND_URL = env.frontend_url.rstrip("/")

# ---------- Email (Gmail SMTP) -------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env.email_host
EMAIL_PORT = env.email_port
EMAIL_HOST_USER = env.email_host_user
EMAIL_HOST_PASSWORD = env.email_host_password
EMAIL_USE_TLS = env.email_use_tls
DEFAULT_FROM_EMAIL = env.default_from_email

# ---------- Django -----------------------------------------------------------

SECRET_KEY = env.secret_key
DEBUG = env.debug
ALLOWED_HOSTS = _parse_list(env.allowed_hosts) or ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.postgres",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    # Local
    "apps.core",
    "apps.users",
    "apps.social",
    "apps.places",
    "apps.checkins",
    "apps.feed",
    "apps.events",
    "apps.gamification",
    "apps.media",
    "apps.ai",
    "apps.geocoding",
    "apps.reviews",
]

AUTH_USER_MODEL = "users.User"

# Argon2 первым — для новых паролей. PBKDF2 — для старых.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------- Database (PostGIS) -----------------------------------------------
import dj_database_url  # noqa: E402

DATABASES = {
    "default": {
        **dj_database_url.parse(env.database_url, conn_max_age=60),
        "ENGINE": "django.contrib.gis.db.backends.postgis",
    }
}

# ---------- Cache (Redis) ---------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env.redis_url,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 0.3,
            "SOCKET_TIMEOUT": 0.3,
            "IGNORE_EXCEPTIONS": True,
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": False,
                "max_connections": 20,
                # health_check_interval должен быть 0 — лишний RTT
                "health_check_interval": 0,
            },
        },
    }
}

DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = "django_redis"

# ---------- Celery ----------------------------------------------------------

CELERY_BROKER_URL = env.redis_url
CELERY_RESULT_BACKEND = env.redis_url
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.media.tasks.*": {"queue": "media"},
    "apps.ai.tasks.*": {"queue": "ai"},
    "apps.users.tasks.*": {"queue": "default"},
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "ru"
FORMS_URLFIELD_ASSUME_HTTPS = True
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- DRF --------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.CursorPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "auth_login": "5/min",
        "auth_register": "5/min",
        "email_verify_request": "5/hour",
        "password_reset_request": "5/hour",
        "google_auth": "10/min",
        "friend_request": "30/hour",
        "user_search": "60/hour",
        "upload_presign": "60/hour",
        "upload_confirm": "120/hour",
        "ai_recommend": "10/hour",
        "geocode": "60/hour",
    },
    "EXCEPTION_HANDLER": "apps.core.exception_handler.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env.secret_key,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AI Reality Map / Go API",
    "DESCRIPTION": (
        "Социальная карта города с AI-разметкой вайба, чек-инами, знакомствами и геймификацией."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Порядок и описания тегов. Новые app'ы получат тег по имени и
    # попадут в конец, в этой секции — то что хочется иметь в красивом порядке.
    "TAGS": [
        {
            "name": "auth",
            "description": "Регистрация, логин, JWT, email-верификация, password reset, Google OAuth",
        },
        {
            "name": "users",
            "description": "Профиль текущего пользователя, онбординг, AI-предпочтения",
        },
        {"name": "social", "description": "Поиск пользователей, друзья, заявки"},
        {"name": "media", "description": "Загрузка фото через presigned URLs в R2"},
        {"name": "places", "description": "Заведения, вайбы, фото"},
        {"name": "geocoding", "description": "Геокодинг через Mapbox"},
        {"name": "checkins", "description": "Чек-ины, лента, лайки"},
        {"name": "events", "description": "Афиша"},
        {"name": "ai", "description": "AI-рекомендации «Куда пойти?»"},
        {"name": "gamification", "description": "Поинты и история транзакций"},
        {"name": "system", "description": "Health/readiness probes, схема API"},
    ],
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.core.openapi.assign_tag_by_path",
    ],
    # Авто-описания операций из docstring view-методов (`def post(self, ...)`)
    "GET_LIB_DOC_EXCLUDES": _default_lib_doc_excludes,
    # Разделить request/response schemas в компонентах (иначе один Place
    # компонент с required-полями только для read-полей)
    "COMPONENT_SPLIT_REQUEST": True,
    # Кнопка Authorize в Swagger UI — JWT bearer
    "SECURITY": [{"bearerAuth": []}],
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
}

# ---------- Logging ---------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "gunicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "gunicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

CORS_ALLOWED_ORIGINS = _parse_list(env.cors_allowed_origins)
CORS_ALLOW_CREDENTIALS = False  # JWT в Authorization header, cookies не используем
# CSRF middleware включён в MIDDLEWARE для админки. API защищён JWT
# (нет SessionAuthentication → CsrfViewMiddleware на API endpoints noop).
CSRF_TRUSTED_ORIGINS = _parse_list(env.cors_allowed_origins)

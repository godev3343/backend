from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import HealthView, ReadinessView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("ready/", ReadinessView.as_view(), name="ready"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/", include("apps.users.urls", namespace="users")),
    path("api/", include("apps.social.urls", namespace="social")),
    path("api/", include("apps.chat.urls", namespace="chat")),
    path("api/", include("apps.media.urls", namespace="media")),
    path("api/", include("apps.places.urls", namespace="places")),
    path("api/", include("apps.geocoding.urls", namespace="geocoding")),
    path("api/", include("apps.checkins.urls", namespace="checkins")),
    path("api/", include("apps.events.urls", namespace="events")),
    path("api/", include("apps.ai.urls", namespace="ai")),
    path("api/", include("apps.gamification.urls", namespace="gamification")),
    path("api/", include("apps.reviews.urls", namespace="reviews")),
    path("api/", include("apps.community.urls", namespace="community")),
    # Deep linking: .well-known/* и landing-страницы шаринга — в корне, не /api/.
    path("", include("apps.deeplinks.urls", namespace="deeplinks")),
]

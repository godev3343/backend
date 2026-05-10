"""Celery-таски для отправки писем."""
from __future__ import annotations

import logging
from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _render_email(template_base: str, ctx: dict) -> tuple[str, str]:
    """Рендерит txt + html для пары шаблонов."""
    text_body = render_to_string(f"emails/{template_base}.txt", ctx)
    html_body = render_to_string(f"emails/{template_base}.html", ctx)
    return text_body, html_body


@shared_task(
    bind=True,
    name="apps.users.tasks.send_verification_email",
    autoretry_for=(SMTPException, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    queue="default",
)
def send_verification_email(self, *, email: str, code: str) -> None:
    """Отправляет письмо с 6-значным кодом верификации email."""
    ctx = {
        "code": code,
        "frontend_url": settings.FRONTEND_URL,
        "ttl_minutes": 15,
    }
    text_body, html_body = _render_email("email_verify", ctx)

    msg = EmailMultiAlternatives(
        subject="Подтверждение email — AI Reality Map",
        body=text_body,
        to=[email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    logger.info("verification_email_sent", extra={"email": email})


@shared_task(
    bind=True,
    name="apps.users.tasks.send_password_reset_email",
    autoretry_for=(SMTPException, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    queue="default",
)
def send_password_reset_email(self, *, email: str, token: str) -> None:
    """Шлёт ссылку на сброс пароля."""
    reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
    ctx = {
        "reset_url": reset_url,
        "frontend_url": settings.FRONTEND_URL,
        "ttl_minutes": 60,
    }
    text_body, html_body = _render_email("password_reset", ctx)

    msg = EmailMultiAlternatives(
        subject="Сброс пароля — AI Reality Map",
        body=text_body,
        to=[email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    logger.info("password_reset_email_sent", extra={"email": email})
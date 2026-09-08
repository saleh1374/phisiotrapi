"""Business logic for OTP generation, SMS delivery and verification."""
import logging
import secrets

from django.conf import settings
from django.utils import timezone

from .models import OTP, User

logger = logging.getLogger(__name__)


def normalize_phone(phone_number: str) -> str:
    """Normalize an Iranian phone number to the canonical 09xxxxxxxxx form."""
    phone = phone_number.replace(" ", "").replace("-", "")
    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        raise ValueError("شماره موبایل معتبر نیست")
    return phone


def _send_sms(phone_number: str, message: str) -> None:
    """Send an SMS through the configured backend.

    `console` backend simply logs the message (development default).
    Production backends (e.g. Kavenegar) can be added here later.
    """
    backend = getattr(settings, "OTP_SMS_BACKEND", "console")
    if backend == "console":
        logger.info("[SMS→%s] %s", phone_number, message)
        print(f"[SMS → {phone_number}] {message}")
    else:
        # Placeholder for a real SMS provider integration.
        logger.warning("OTP_SMS_BACKEND=%s is not implemented yet; SMS not sent.", backend)


def request_otp(phone_number: str) -> None:
    """Generate a fresh 6-digit OTP and send it to the given phone number."""
    phone = normalize_phone(phone_number)

    # Invalidate any previous, still-unused codes for this phone.
    OTP.objects.filter(phone_number=phone, is_used=False).update(is_used=True)

    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = OTP.objects.create(
        phone_number=phone,
        code=code,
        expires_at=timezone.now() + timezone.timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
    )
    _send_sms(phone, f"کد ورود شما به کلینیک فیزیوتراپی: {code}")
    return otp.id


def verify_otp(phone_number: str, code: str) -> User:
    """Verify an OTP code. Raises ValueError on any failure.

    Returns the (possibly just-created) user for this phone number.
    """
    phone = normalize_phone(phone_number)
    otp = (
        OTP.objects.filter(phone_number=phone, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise ValueError("کد منقضی شده است؛ لطفاً کد جدیدی درخواست کنید")

    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise ValueError("تعداد تلاشهای ناموفق زیاد بود؛ کد جدیدی درخواست کنید")

    if not otp.is_valid_code(code):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise ValueError("کد وارد شده صحیح نیست")

    otp.is_used = True
    otp.save(update_fields=["is_used"])

    # Register the user on first login (auto sign-up by phone number).
    user, _ = User.objects.get_or_create(
        phone_number=phone,
        defaults={"is_active": True},
    )
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    return user
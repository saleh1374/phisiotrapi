from rest_framework.throttling import ScopedRateThrottle


class OTPThrottle(ScopedRateThrottle):
    """Limits OTP requests per minute (brute-force protection)."""

    scope = "otp"


class LoginThrottle(ScopedRateThrottle):
    """Limits password login attempts per minute."""

    scope = "login"
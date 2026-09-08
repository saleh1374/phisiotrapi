from rest_framework.test import APITestCase as TestCase
from django.urls import reverse

from accounts.models import OTP, User


class OTPAuthFlowTests(TestCase):
    def _request_otp(self, phone: str = "09123456789"):
        resp = self.client.post(
            reverse("otp-request"),
            data={"phone_number": phone},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        return OTP.objects.filter(phone_number=phone, is_used=False).latest("created_at")

    def test_otp_request_and_verify_registers_user(self):
        otp = self._request_otp()

        resp = self.client.post(
            reverse("otp-verify"),
            data={
                "phone_number": "09123456789",
                "code": otp.code,
                "full_name": "تست کاربر",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertIn("tokens", data)
        self.assertIn("access", data["tokens"])
        self.assertEqual(data["user"]["role"], "patient")

        user = User.objects.get(phone_number="09123456789")
        self.assertEqual(user.full_name, "تست کاربر")
        self.assertTrue(user.is_active)

    def test_otp_is_single_use(self):
        otp = self._request_otp()
        payload = {
            "phone_number": "09123456789",
            "code": otp.code,
        }
        first = self.client.post(reverse("otp-verify"), data=payload, format="json")
        self.assertEqual(first.status_code, 200)

        # Replaying the same code must fail.
        replay = self.client.post(reverse("otp-verify"), data=payload, format="json")
        self.assertEqual(replay.status_code, 400)

    def test_wrong_code_fails_and_counts_attempts(self):
        otp = self._request_otp()

        resp = self.client.post(
            reverse("otp-verify"),
            data={"phone_number": "09123456789", "code": "000000"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        otp.refresh_from_db()
        self.assertEqual(otp.attempts, 1)
        self.assertFalse(otp.is_used)

    def test_invalid_phone_rejected(self):
        resp = self.client.post(
            reverse("otp-request"),
            data={"phone_number": "12345"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_login(self):
        user = User.objects.create_user(phone_number="09120000000", password="secret123")
        user.role = User.Role.ADMIN
        user.save()

        resp = self.client.post(
            reverse("login"),
            data={"phone_number": "09120000000", "password": "secret123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("access", resp.json()["tokens"])

        bad = self.client.post(
            reverse("login"),
            data={"phone_number": "09120000000", "password": "wrong"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

    def test_me_requires_auth(self):
        resp = self.client.get(reverse("me"))
        self.assertEqual(resp.status_code, 401)


class UserManagerTests(TestCase):
    def test_phone_normalization(self):
        user = User.objects.create_user(phone_number="+98 912 000 0000", password="x")
        self.assertEqual(user.phone_number, "09120000000")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(phone_number="09121111111", password="x")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)
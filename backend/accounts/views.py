from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import User
from .serializers import (
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordLoginSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
)
from .throttles import LoginThrottle, OTPThrottle


def _tokens_for(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class OTPRequestView(APIView):
    """Step 1 of the OTP flow: request a 6-digit code for a phone number."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPThrottle]
    serializer_class = OTPRequestSerializer

    @extend_schema(
        request=OTPRequestSerializer,
        responses={200: OpenApiResponse(description="کد پیامک شد")},
    )
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_otp(serializer.validated_data["phone_number"])
        return Response(
            {"detail": "کد تایید پیامک شد"},
            status=status.HTTP_200_OK,
        )


class OTPVerifyView(APIView):
    """Step 2 of the OTP flow: verify the code and receive JWT tokens.

    New phone numbers are auto-registered (patient role) — OTP doubles as
    both login and registration. Idempotent per code: a used code can never
    be replayed.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPThrottle]
    serializer_class = OTPVerifySerializer

    @extend_schema(
        request=OTPVerifySerializer,
        responses={200: UserSerializer},
    )
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = services.verify_otp(data["phone_number"], data["code"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Capture the full name on first registration.
        if data.get("full_name") and not user.full_name:
            user.full_name = data["full_name"]
            user.save(update_fields=["full_name"])

        return Response(
            {
                "tokens": _tokens_for(user),
                "user": UserSerializer(user).data,
                "is_new": user.created_at == user.last_login,
            },
            status=status.HTTP_200_OK,
        )


class PasswordLoginView(APIView):
    """Password-based login for admins/doctors (patients use OTP)."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]
    serializer_class = PasswordLoginSerializer

    @extend_schema(
        request=PasswordLoginSerializer,
        responses={200: UserSerializer},
    )
    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = authenticate(
            request,
            username=data["phone_number"],
            password=data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "شماره موبایل یا رمز عبور اشتباه است"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "tokens": _tokens_for(user),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """View / update the currently authenticated user's profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ProfileUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        # Preserve the full serializer output in the response.
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = ProfileUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(instance).data)
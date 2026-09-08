from rest_framework import serializers

from . import services
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Public user representation returned to the frontend."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "phone_number",
            "email",
            "role",
            "role_display",
            "profile_pic",
            "specialty",
            "medical_license_number",
            "bio",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "phone_number", "role", "is_active", "created_at"]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Allows a user to update their own profile (phone is immutable)."""

    class Meta:
        model = User
        fields = ["full_name", "email", "national_code", "profile_pic", "bio"]
        extra_kwargs = {
            "email": {"required": False, "allow_null": True},
            "national_code": {"required": False, "allow_null": True},
        }


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=16, write_only=True)

    def validate_phone_number(self, value: str) -> str:
        try:
            return services.normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=16, write_only=True)
    code = serializers.CharField(min_length=4, max_length=6, write_only=True)
    full_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_phone_number(self, value: str) -> str:
        try:
            return services.normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_code(self, value: str) -> str:
        if not value.strip().isdigit():
            raise serializers.ValidationError("کد باید فقط شامل عدد باشد")
        return value.strip()


class PasswordLoginSerializer(serializers.Serializer):
    """Password-based login (used by admins/doctors)."""

    phone_number = serializers.CharField(max_length=16, write_only=True)
    password = serializers.CharField(write_only=True)

    def validate_phone_number(self, value: str) -> str:
        try:
            return services.normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
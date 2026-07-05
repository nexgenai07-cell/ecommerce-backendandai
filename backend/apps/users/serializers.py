# PATH: apps/users/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, UserSession


class RegisterSerializer(serializers.ModelSerializer):
    """
    Used for public registration.
    Role is always forced to 'customer' — admin cannot be created here.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['name', 'email', 'phone', 'password', 'confirm_password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        # role is never taken from input — always customer
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data['name'],
            phone=validated_data.get('phone', ''),
            role='customer',
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError('Invalid email or password.')

        if not user.is_active:
            raise serializers.ValidationError('This account has been deactivated.')

        data['user'] = user
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    """Used for GET /me/ and PUT /me/update/"""

    two_factor_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'role',
            'email_verified',
            'two_factor_enabled',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'email',
            'role',
            'email_verified',
            'two_factor_enabled',
            'created_at',
        ]

    def get_two_factor_enabled(self, obj):
        try:
            return obj.two_factor.is_enabled
        except:
            return False

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            # Security note: in production, many APIs return success even if
            # email doesn't exist, to avoid leaking which emails are registered.
            # For a learning/client project, explicit error is fine and clearer.
            raise serializers.ValidationError('No account found with this email.')
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    uid = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """
    Used by ChangePasswordView.
    current_password is checked against the logged-in user's saved (hashed) password.
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            # check_password() safely compares the plain text input against
            # the hashed password stored in the database — this is the
            # standard, secure way to verify a password in Django.
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, data):
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError({
                'new_password': 'New password must be different from the current password.'
            })
        return data


class DeleteAccountSerializer(serializers.Serializer):
    """Requires the user's password as confirmation before deleting — prevents
    accidental deletion or deletion by someone who briefly has device access."""
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Incorrect password.')
        return value


class UserSessionSerializer(serializers.ModelSerializer):
    """Used by GET /sessions/ to list a user's active logins (devices/browsers)."""

    # FIX: "is_current" field ADD kiya gaya — pehle ye field exist hi nahi
    # karta tha, jab ke Requirements doc ke sample response mein
    # "is_current": true documented hai. Frontend isi field se batata hai
    # ke kaunsa device "this device" hai (jise sign-out button na dikhaye).
    # Current session ka pata request ke access token ke jti se chalta hai
    # (dekho views.py -> SessionListView / create_session_record).
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = ['id', 'device', 'browser', 'location', 'ip_address', 'is_current', 'last_active', 'created_at']

    def get_is_current(self, obj):
        request = self.context.get('request')
        if not request or not getattr(request, 'auth', None):
            return False
        try:
            current_access_jti = str(request.auth['jti'])
        except (KeyError, TypeError):
            return False
        return obj.access_jti == current_access_jti
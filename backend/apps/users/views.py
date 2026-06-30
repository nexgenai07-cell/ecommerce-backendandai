# PATH: apps/users/views.py

from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from user_agents import parse as parse_user_agent

from .models import User, UserSession, EmailVerification
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    DeleteAccountSerializer,
    UserSessionSerializer,
)


def get_tokens_for_user(user):
    """Helper — generates access + refresh token pair for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def get_client_ip(request):
    """Helper — reads the real client IP, accounting for proxies/load balancers"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def create_session_record(request, user, refresh_token):
    """
    Called once at login. Parses the browser's User-Agent header to get a
    human-readable device/browser name, and stores the refresh token's jti
    (its unique ID) so this specific session can be revoked later.
    """
    ua_string = request.META.get('HTTP_USER_AGENT', '')
    ua = parse_user_agent(ua_string)

    device = f'{ua.device.family}' if ua.device.family != 'Other' else f'{ua.os.family} Device'
    browser = f'{ua.browser.family} {ua.browser.version_string}'

    UserSession.objects.create(
        user=user,
        refresh_jti=str(refresh_token['jti']),
        device=device,
        browser=browser,
        ip_address=get_client_ip(request),
        location='Unknown',  # IP-to-location lookup needs a 3rd-party service (e.g. ipapi.co) — left as a TODO
    )


def send_verification_email(user):
    """Shared helper — called both at registration and from the resend endpoint"""
    verification = EmailVerification.create_for_user(user)
    verify_link = f'http://localhost:5173/verify-email/{verification.token}/'

    send_mail(
        subject='Verify your email address',
        message=f'Click the link to verify your email: {verify_link}\n\nThis link is valid for 24 hours.',
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
        recipient_list=[user.email],
        fail_silently=False,  # TEMP: False taake Vercel logs mein asal error dikhe (debugging)
    )


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/
    Public registration — role is always 'customer'.
    Automatically sends a verification email right after the account is created.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = get_tokens_for_user(user)

        try:
            send_verification_email(user)
        except Exception:
            pass  # registration must still succeed even if email sending fails

        return Response({
            'message': 'Registration successful. Please check your email to verify your account.',
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Also creates a UserSession row on every successful login, so the
    "Active Sessions" feature has real data to show (device, browser, IP).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        tokens = {'access': str(refresh.access_token), 'refresh': str(refresh)}

        create_session_record(request, user, refresh)

        return Response({
            'message': 'Login successful.',
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the refresh token so it cannot be reused.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'error': 'Invalid or expired refresh token.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {'message': 'Logged out successfully.'},
            status=status.HTTP_200_OK
        )


class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password-reset/
    Sends a reset link to the user's email. Link is valid for 24 hours.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = User.objects.get(email=email)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_link = f'http://localhost:5173/reset-password/{uid}/{token}/'

        send_mail(
            subject='Password Reset Request',
            message=f'Click the link to reset your password: {reset_link}\n\nThis link is valid for 24 hours.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[email],
            fail_silently=False,  # TEMP: False taake Vercel logs mein asal error dikhe (debugging)
        )

        return Response(
            {'message': 'Password reset link has been sent to your email.'},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password-reset/confirm/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'error': 'Invalid reset link.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'Reset link is invalid or has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {'message': 'Password has been reset successfully.'},
            status=status.HTTP_200_OK
        )


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/auth/me/        -> view own profile
    PUT /api/v1/auth/me/update/ -> update own profile
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/

    Requires the user to prove they know their CURRENT password before
    setting a new one — this prevents someone who has briefly accessed
    a logged-in device from locking the real owner out of their account.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response(
            {'message': 'Password changed successfully.'},
            status=status.HTTP_200_OK
        )


class DeleteAccountView(APIView):
    """
    DELETE /api/v1/auth/me/delete/

    This is a SOFT delete (is_active=False), not a hard delete from the database.
    Why soft delete:
      - Order history, payments, and returns linked to this user must be kept
        for accounting/audit purposes — deleting the User row would either
        break those records (ForeignKey error) or silently delete order history.
      - If the customer comes back later or disputes a charge, the data is
        still there for the admin to look up.
      - This matches how almost every real ecommerce platform handles "delete
        account" — the account is deactivated, not instantly wiped.

    After this call: the user's tokens stop working (is_active=False makes
    authentication fail), and they cannot log in again unless an admin
    reactivates the account.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.is_active = False
        user.save()

        # Blacklist all of this user's outstanding refresh tokens so old
        # tokens can't be used even before they'd naturally expire.
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(
            {'message': 'Account deleted successfully.'},
            status=status.HTTP_200_OK
        )


class SessionListView(generics.ListAPIView):
    """
    GET /api/v1/auth/sessions/
    Lists every device/browser this user is currently logged in from.
    """
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)


class RevokeAllSessionsView(APIView):
    """
    POST /api/v1/auth/sessions/revoke-all/
    Blacklists every refresh token this user has ever been issued and deletes
    all session records — effectively logs the user out everywhere at once.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

        user = request.user
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        UserSession.objects.filter(user=user).delete()

        return Response(
            {'message': 'All sessions have been signed out.'},
            status=status.HTTP_200_OK
        )
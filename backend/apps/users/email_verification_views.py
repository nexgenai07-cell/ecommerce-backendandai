# PATH: apps/users/email_verification_views.py
# New file — separate from views.py for organization.

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings

from .models import EmailVerification


class SendVerificationEmailView(APIView):
    """
    POST /api/v1/auth/send-verification-email/

    Sends a verification link to the logged-in user's email. Can be called:
      - Automatically right after registration (see note in RegisterView below)
      - Manually if the user wants to resend (e.g. "Resend email" button)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.email_verified:
            return Response({'message': 'Email is already verified.'}, status=status.HTTP_200_OK)

        verification = EmailVerification.create_for_user(user)

        # Same pattern as password reset — points to a frontend page that
        # will read the token from the URL and call the GET endpoint below
        verify_link = f'http://localhost:5173/verify-email/{verification.token}/'

        send_mail(
            subject='Verify your email address',
            message=f'Click the link to verify your email: {verify_link}\n\nThis link is valid for 24 hours.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
            fail_silently=False,  # TEMP: False taake Vercel logs mein asal error dikhe (debugging)
        )

        return Response(
            {'message': 'Verification email has been sent.'},
            status=status.HTTP_200_OK
        )


class VerifyEmailView(APIView):
    """
    GET /api/v1/auth/verify-email/?token=xxx

    No authentication required — the token itself IS the proof of identity
    here (it was emailed to the user's own inbox). This matches the
    password-reset-confirm pattern already used elsewhere in this project.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response({'error': 'token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification = EmailVerification.objects.get(token=token)
        except EmailVerification.DoesNotExist:
            return Response({'error': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not verification.is_valid():
            return Response({'error': 'This verification link has expired or already been used.'}, status=status.HTTP_400_BAD_REQUEST)

        user = verification.user
        user.email_verified = True
        user.save()

        verification.is_used = True
        verification.save()

        return Response({'message': 'Email verified successfully.'}, status=status.HTTP_200_OK)
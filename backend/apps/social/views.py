# PATH: apps/social/views.py

from django.utils import timezone
from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.permissions import IsAdmin
from .models import SocialAccount, SocialPost, SocialPostAnalytics
from .serializers import SocialAccountSerializer, SocialPostSerializer, SocialPostCreateSerializer
from apps.notifications.utils import create_notification

class SocialPostViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/social/posts/                -> list all posts (admin only)
    POST   /api/v1/social/posts/create/          -> manually create a post (admin only)
    GET    /api/v1/social/posts/{id}/            -> retrieve single post
    PUT    /api/v1/social/posts/{id}/approve/    -> approve a pending post
    PUT    /api/v1/social/posts/{id}/reject/     -> reject a pending post
    PUT    /api/v1/social/posts/{id}/schedule/   -> set a scheduled_at time
    DELETE /api/v1/social/posts/{id}/            -> delete a post
    GET    /api/v1/social/posts/calendar/        -> posts grouped for calendar view

    NOTE: actual publishing to Instagram/Facebook happens via a Celery task
    (publish_scheduled_posts) — this is built later alongside the Social Agent.
    """
    queryset = SocialPost.objects.select_related('product', 'analytics').all()
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.action == 'create':
            return SocialPostCreateSerializer
        return SocialPostSerializer

    @action(detail=True, methods=['put'], url_path='approve')
    def approve(self, request, pk=None):
        """Moves a pending post to 'approved' status."""
        post = self.get_object()
        post.status = 'approved'
        post.save()
        return Response(SocialPostSerializer(post).data)

    @action(detail=True, methods=['put'], url_path='reject')
    def reject(self, request, pk=None):
        """Moves a pending post to 'rejected' status — it will not be published."""
        post = self.get_object()
        post.status = 'rejected'
        post.save()
        return Response(SocialPostSerializer(post).data)

    @action(detail=True, methods=['put'], url_path='schedule')
    def schedule(self, request, pk=None):
        """
        Sets the scheduled_at time and moves status to 'scheduled'.
        Body: { "scheduled_at": "2026-06-25T18:00:00Z" }
        """
        post = self.get_object()
        scheduled_at = request.data.get('scheduled_at')

        if not scheduled_at:
            return Response({'error': 'scheduled_at is required.'}, status=status.HTTP_400_BAD_REQUEST)

        post.scheduled_at = scheduled_at
        post.status = 'scheduled'
        post.save()
        return Response(SocialPostSerializer(post).data)

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar(self, request):
        """
        Returns scheduled/published posts — frontend groups these by date
        to build the month calendar view.
        """
        qs = self.get_queryset().filter(status__in=['scheduled', 'published'])
        return Response(SocialPostSerializer(qs, many=True).data)


class SocialAccountViewSet(viewsets.ModelViewSet):
    """
    GET  /api/v1/social/accounts/          -> list connected accounts (admin only)
    POST /api/v1/social/accounts/connect/   -> connect a new Instagram/Facebook account
    """
    queryset = SocialAccount.objects.all()
    serializer_class = SocialAccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def perform_create(self, serializer):
        # Single-store setup — always attach the one store that exists.
        from apps.stores.models import Store
        serializer.save(store=Store.objects.first())


class SocialPostAnalyticsView(generics.RetrieveAPIView):
    """
    GET /api/v1/social/analytics/{post_id}/

    Returns engagement metrics (likes, comments, shares, reach) for a post.
    Actual numbers are filled in daily by a Celery Beat task (fetch_social_analytics)
    that calls the Instagram/Facebook Graph API.
    """
    queryset = SocialPostAnalytics.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    lookup_url_kwarg = 'post_id'
    lookup_field = 'post_id'

    def get_serializer_class(self):
        from .serializers import SocialPostAnalyticsSerializer
        return SocialPostAnalyticsSerializer

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .choices import PROFILE_ROLE_STUDENT
from .models import (
    Annotation,
    AnnotationCampaign,
    MonitoringItem,
    MonitoringRun,
    MonitoringSource,
    OmsuArea,
    OmsuDashboardSnapshot,
    OmsuLatestComment,
    ScoreEvent,
    SourceRecord,
    UserProfile,
)
from .permissions import user_is_annotation_admin, user_is_project_superadmin


def user_can_approve_profiles(user):
    return user_is_annotation_admin(user)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_approved", "approved_by", "approved_at", "created_at")
    list_filter = ("role", "is_approved")
    search_fields = ("user__username", "user__first_name", "user__last_name", "public_name")
    actions = ("approve_profiles",)
    readonly_fields = ("approved_by", "approved_at", "created_at")

    def approve_profiles(self, request, queryset):
        if not user_can_approve_profiles(request.user):
            raise PermissionDenied("Недостаточно прав для утверждения учетных записей.")
        if not user_is_project_superadmin(request.user):
            queryset = queryset.filter(role=PROFILE_ROLE_STUDENT)
        updated = 0
        for profile in queryset:
            profile.is_approved = True
            profile.approved_by = request.user
            profile.approved_at = timezone.now()
            profile.save(update_fields=["is_approved", "approved_by", "approved_at"])
            updated += 1
        self.message_user(request, f"Утверждено учетных записей: {updated}", messages.SUCCESS)

    approve_profiles.short_description = "Утвердить выбранные учетные записи"

    def has_module_permission(self, request):
        return user_can_approve_profiles(request.user) or super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return user_can_approve_profiles(request.user) or super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return user_can_approve_profiles(request.user) or super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return user_is_project_superadmin(request.user)

    def has_delete_permission(self, request, obj=None):
        return user_is_project_superadmin(request.user)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not user_is_project_superadmin(request.user):
            fields.extend(["user", "role", "public_name"])
        return tuple(fields)

    def save_model(self, request, obj, form, change):
        if not user_can_approve_profiles(request.user):
            raise PermissionDenied("Недостаточно прав для изменения доступа.")
        if not user_is_project_superadmin(request.user):
            if obj.role != PROFILE_ROLE_STUDENT:
                raise PermissionDenied("Администратор разметки может утверждать только студентов.")
            if change:
                original = UserProfile.objects.get(pk=obj.pk)
                if original.role != PROFILE_ROLE_STUDENT:
                    raise PermissionDenied("Администратор разметки может утверждать только студентов.")
        if obj.is_approved and not obj.approved_by:
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(SourceRecord)
class SourceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_text",
        "group_name",
        "source_name",
        "is_active",
        "sampling_pool",
        "jkh_candidate_score",
        "times_seen",
        "reserved_by",
        "reserved_until",
        "imported_at",
    )
    list_filter = ("is_active", "sampling_pool", "source_name", "group_name", "reserved_by")
    search_fields = ("text", "post_text", "source_hash", "external_id", "source_url")
    readonly_fields = (
        "source_hash",
        "jkh_candidate_score",
        "jkh_candidate_reason",
        "sampling_updated_at",
        "reserved_by",
        "reserved_until",
        "imported_at",
    )

    def short_text(self, obj):
        return obj.text[:90]


@admin.register(AnnotationCampaign)
class AnnotationCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "is_active",
        "candidate_ratio",
        "candidate_count",
        "control_count",
        "score_threshold",
        "updated_at",
    )
    readonly_fields = ("candidate_count", "control_count", "updated_at")

    def has_module_permission(self, request):
        return user_is_annotation_admin(request.user) or super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return user_is_annotation_admin(request.user) or super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return user_is_project_superadmin(request.user)

    def has_change_permission(self, request, obj=None):
        return user_is_project_superadmin(request.user)

    def has_delete_permission(self, request, obj=None):
        return user_is_project_superadmin(request.user)


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student",
        "record",
        "jkh_relevance",
        "jkh_topic",
        "is_deleted_post_report",
        "status",
        "submitted_at",
        "reviewed_by",
    )
    list_filter = (
        "status",
        "is_deleted_post_report",
        "jkh_relevance",
        "jkh_topic",
        "sentiment",
        "appeal_type",
        "responsible_party",
    )
    search_fields = ("record__text", "record__post_text", "student__username", "student_comment", "review_comment")
    readonly_fields = ("submitted_at", "updated_at", "reviewed_at")


@admin.register(ScoreEvent)
class ScoreEventAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "kind", "points", "created_by", "annotation", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("student__username", "reason", "annotation__record__text")
    readonly_fields = ("created_at",)


@admin.register(OmsuArea)
class OmsuAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "area_type", "region", "head_name", "display_order", "is_active", "updated_at")
    list_filter = ("is_active", "area_type", "region")
    search_fields = ("name", "slug", "head_name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("updated_at",)


@admin.register(OmsuDashboardSnapshot)
class OmsuDashboardSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "area",
        "omsu_score",
        "previous_omsu_score",
        "omsu_negative_probability",
        "comments_total",
        "comments_last_day",
        "generated_at",
    )
    list_filter = ("generated_at",)
    search_fields = ("area__name", "area__slug")
    readonly_fields = ("updated_at",)


@admin.register(OmsuLatestComment)
class OmsuLatestCommentAdmin(admin.ModelAdmin):
    list_display = ("area", "sentiment", "omsu_score", "source_name", "published_at", "received_at")
    list_filter = ("sentiment", "source_name", "published_at")
    search_fields = ("area__name", "text", "source_name")


@admin.register(MonitoringSource)
class MonitoringSourceAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "area",
        "screen_name",
        "is_active",
        "last_success_at",
        "display_order",
        "updated_at",
    )
    list_filter = ("is_active", "kind", "area")
    search_fields = ("slug", "title", "screen_name", "url", "last_error")
    readonly_fields = ("last_success_at", "last_error", "parser_state", "created_at", "updated_at")


@admin.register(MonitoringRun)
class MonitoringRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "started_at",
        "finished_at",
        "lookback_minutes",
        "sources_total",
        "sources_ok",
        "sources_failed",
        "posts_found",
        "comments_found",
        "items_created",
        "items_existing",
        "items_analyzed",
        "dry_run",
    )
    list_filter = ("status", "dry_run", "update_dashboard", "started_at")
    readonly_fields = (
        "started_at",
        "finished_at",
        "sources_total",
        "sources_ok",
        "sources_failed",
        "posts_found",
        "comments_found",
        "items_created",
        "items_existing",
        "items_analyzed",
        "error_log",
        "meta",
    )


@admin.register(MonitoringItem)
class MonitoringItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "area",
        "source",
        "item_type",
        "short_text",
        "published_at",
        "omsu_score",
        "omsu_negative_probability",
        "omsu_decision",
        "analyzed_at",
    )
    list_filter = ("item_type", "area", "source", "omsu_decision", "published_at", "analyzed_at")
    search_fields = ("text", "post_text", "source_url", "external_id", "author_name")
    readonly_fields = (
        "source_hash",
        "fetched_at",
        "raw",
        "cleaned_meta",
        "taxonomy",
        "taxonomy_confidence",
        "omsu_score",
        "omsu_impact_class",
        "omsu_negative_probability",
        "omsu_decision",
        "omsu_confidence_band",
        "omsu_score_reason",
        "analyzed_at",
    )

    def short_text(self, obj):
        return obj.text[:90]

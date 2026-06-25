import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .choices import (
    ANNOTATION_STATUS_CHOICES,
    ANNOTATION_STATUS_SUBMITTED,
    APPEAL_TYPE_CHOICES,
    AUTHORITY_ASPECT_CHOICES,
    JKH_TOPIC_CHOICES,
    PROFILE_ROLE_CHOICES,
    PROFILE_ROLE_STUDENT,
    QUALITY_CHOICES,
    RELEVANCE_CHOICES,
    RESPONSIBLE_PARTY_CHOICES,
    SAMPLING_POOL_CHOICES,
    SAMPLING_POOL_GENERAL,
    SARCASM_CHOICES,
    SCORE_KIND_CHOICES,
    SENTIMENT_CHOICES,
)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=PROFILE_ROLE_CHOICES, default=PROFILE_ROLE_STUDENT)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_profiles",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    public_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def can_work(self):
        return self.is_approved or (self.user.is_superuser and self.user.username == "oldskull")

    def approve(self, admin_user):
        self.is_approved = True
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.save(update_fields=["is_approved", "approved_by", "approved_at"])


class SourceRecord(models.Model):
    text = models.TextField()
    post_text = models.TextField(blank=True)
    source_hash = models.CharField(max_length=64, unique=True)
    source_name = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    group_name = models.CharField(max_length=255, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    times_seen = models.PositiveIntegerField(default=0)
    sampling_pool = models.CharField(
        max_length=20,
        choices=SAMPLING_POOL_CHOICES,
        default=SAMPLING_POOL_GENERAL,
        db_index=True,
    )
    jkh_candidate_score = models.PositiveSmallIntegerField(default=0)
    jkh_candidate_reason = models.TextField(blank=True)
    sampling_updated_at = models.DateTimeField(null=True, blank=True)
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reserved_source_records",
    )
    reserved_until = models.DateTimeField(null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["times_seen", "imported_at"]

    def __str__(self):
        return self.text[:80]

    @staticmethod
    def build_hash(text, post_text="", external_id=""):
        payload = "\n".join([external_id.strip(), text.strip(), post_text.strip()])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def has_active_reservation(self, now=None):
        now = now or timezone.now()
        return bool(self.reserved_by_id and self.reserved_until and self.reserved_until > now)

    def is_reserved_by_other(self, user, now=None):
        return self.has_active_reservation(now) and self.reserved_by_id != user.id

    def reserve_for(self, user, minutes=15):
        self.reserved_by = user
        self.reserved_until = timezone.now() + timedelta(minutes=minutes)

    def clear_reservation(self):
        self.reserved_by = None
        self.reserved_until = None


class AnnotationCampaign(models.Model):
    key = models.CharField(max_length=60, unique=True, default="jkh_enrichment")
    title = models.CharField(max_length=160, default="Целевой добор ЖКХ")
    is_active = models.BooleanField(default=False)
    candidate_ratio = models.PositiveIntegerField(default=100)
    candidate_count = models.PositiveIntegerField(default=0)
    control_count = models.PositiveIntegerField(default=0)
    score_threshold = models.PositiveSmallIntegerField(default=7)
    random_seed = models.PositiveIntegerField(default=42)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        state = "активна" if self.is_active else "остановлена"
        return f"{self.title} ({state})"


class Annotation(models.Model):
    record = models.ForeignKey(SourceRecord, on_delete=models.CASCADE, related_name="annotations")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="annotations")
    jkh_relevance = models.CharField(max_length=20, choices=RELEVANCE_CHOICES)
    jkh_topic = models.CharField(max_length=40, choices=JKH_TOPIC_CHOICES)
    authority_aspect = models.CharField(max_length=40, choices=AUTHORITY_ASPECT_CHOICES)
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES)
    appeal_type = models.CharField(max_length=30, choices=APPEAL_TYPE_CHOICES)
    responsible_party = models.CharField(max_length=40, choices=RESPONSIBLE_PARTY_CHOICES)
    sarcasm = models.CharField(max_length=20, choices=SARCASM_CHOICES)
    quality = models.CharField(max_length=30, choices=QUALITY_CHOICES, default="normal")
    student_comment = models.TextField(blank=True)
    is_deleted_post_report = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=ANNOTATION_STATUS_CHOICES,
        default=ANNOTATION_STATUS_SUBMITTED,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_annotations",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["submitted_at"]
        constraints = [
            models.UniqueConstraint(fields=["record", "student"], name="unique_annotation_per_student_record")
        ]

    def __str__(self):
        return f"{self.student.username}: {self.record_id} ({self.get_status_display()})"


class ScoreEvent(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="score_events")
    annotation = models.ForeignKey(
        Annotation,
        on_delete=models.CASCADE,
        related_name="score_events",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_scores")
    kind = models.CharField(max_length=20, choices=SCORE_KIND_CHOICES)
    points = models.IntegerField()
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.points >= 0 else ""
        return f"{self.student.username}: {sign}{self.points}"


class OmsuArea(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    area_type = models.CharField(max_length=80, default="Муниципальное образование")
    region = models.CharField(max_length=120, default="Нижегородская область")
    head_name = models.CharField(max_length=160, blank=True)
    leadership = models.JSONField(default=list, blank=True)
    territory_area_km2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    population = models.PositiveIntegerField(null=True, blank=True)
    image_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    geometry = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class OmsuDashboardSnapshot(models.Model):
    area = models.OneToOneField(OmsuArea, on_delete=models.CASCADE, related_name="snapshot")
    omsu_score = models.IntegerField(default=0)
    previous_omsu_score = models.IntegerField(default=0)
    omsu_negative_probability = models.FloatField(default=0.0)
    comments_total = models.PositiveIntegerField(default=0)
    comments_last_day = models.PositiveIntegerField(default=0)
    negative_total = models.PositiveIntegerField(default=0)
    neutral_total = models.PositiveIntegerField(default=0)
    positive_total = models.PositiveIntegerField(default=0)
    top_topics = models.JSONField(default=list, blank=True)
    charts = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["area__display_order", "area__name"]

    def __str__(self):
        return f"{self.area.name}: {self.omsu_score:+d}"


class OmsuLatestComment(models.Model):
    area = models.ForeignKey(OmsuArea, on_delete=models.CASCADE, related_name="latest_comments")
    text = models.TextField()
    sentiment = models.CharField(max_length=20, default="neutral")
    omsu_score = models.IntegerField(default=0)
    source_name = models.CharField(max_length=160, blank=True)
    source_url = models.URLField(blank=True)
    published_at = models.DateTimeField(default=timezone.now)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-published_at", "-received_at"]

    def __str__(self):
        return f"{self.area.name}: {self.text[:80]}"


class MonitoringSource(models.Model):
    SOURCE_KIND_VK_GROUP = "vk_group"

    SOURCE_KIND_CHOICES = [
        (SOURCE_KIND_VK_GROUP, "VK group"),
    ]

    slug = models.SlugField(max_length=120, unique=True)
    area = models.ForeignKey(
        OmsuArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="monitoring_sources",
    )
    kind = models.CharField(max_length=30, choices=SOURCE_KIND_CHOICES, default=SOURCE_KIND_VK_GROUP)
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=500)
    screen_name = models.CharField(max_length=160, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    parser_state = models.JSONField(default=dict, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "slug"]

    def __str__(self):
        return self.title or self.screen_name or self.slug


class MonitoringRun(models.Model):
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_FAILED, "Failed"),
    ]

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING, db_index=True)
    lookback_minutes = models.PositiveIntegerField(default=120)
    max_sources = models.PositiveIntegerField(default=0)
    max_posts_per_source = models.PositiveIntegerField(default=0)
    max_comments_per_post = models.PositiveIntegerField(default=0)
    sources_total = models.PositiveIntegerField(default=0)
    sources_ok = models.PositiveIntegerField(default=0)
    sources_failed = models.PositiveIntegerField(default=0)
    posts_found = models.PositiveIntegerField(default=0)
    comments_found = models.PositiveIntegerField(default=0)
    items_created = models.PositiveIntegerField(default=0)
    items_existing = models.PositiveIntegerField(default=0)
    items_analyzed = models.PositiveIntegerField(default=0)
    update_dashboard = models.BooleanField(default=False)
    dry_run = models.BooleanField(default=False)
    error_log = models.JSONField(default=list, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"MonitoringRun {self.id or 'new'} ({self.status})"

    def finish(self, status: str):
        self.status = status
        self.finished_at = timezone.now()


class MonitoringItem(models.Model):
    ITEM_POST = "post"
    ITEM_COMMENT = "comment"

    ITEM_TYPE_CHOICES = [
        (ITEM_POST, "Post"),
        (ITEM_COMMENT, "Comment"),
    ]

    source = models.ForeignKey(MonitoringSource, on_delete=models.CASCADE, related_name="items")
    run = models.ForeignKey(
        MonitoringRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    area = models.ForeignKey(
        OmsuArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="monitoring_items",
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, db_index=True)
    external_id = models.CharField(max_length=255, blank=True)
    source_hash = models.CharField(max_length=64, unique=True)
    source_url = models.URLField(max_length=500, blank=True)
    post_external_id = models.CharField(max_length=255, blank=True)
    post_url = models.URLField(max_length=500, blank=True)
    text = models.TextField()
    post_text = models.TextField(blank=True)
    author_name = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_at_raw = models.CharField(max_length=255, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now, db_index=True)
    raw = models.JSONField(default=dict, blank=True)
    cleaned_meta = models.JSONField(default=dict, blank=True)
    taxonomy = models.JSONField(default=dict, blank=True)
    taxonomy_confidence = models.JSONField(default=dict, blank=True)
    omsu_score = models.IntegerField(default=0)
    omsu_impact_class = models.CharField(max_length=40, blank=True)
    omsu_negative_probability = models.FloatField(default=0.0)
    omsu_decision = models.CharField(max_length=40, blank=True)
    omsu_confidence_band = models.CharField(max_length=40, blank=True)
    omsu_score_reason = models.TextField(blank=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-fetched_at", "id"]
        indexes = [
            models.Index(fields=["source", "item_type", "external_id"]),
            models.Index(fields=["area", "published_at"]),
            models.Index(fields=["omsu_decision", "published_at"]),
        ]

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.text[:80]}"

    @staticmethod
    def build_hash(source_url="", external_id="", text="", post_text=""):
        payload = "\n".join(
            [
                str(source_url or "").strip(),
                str(external_id or "").strip(),
                str(text or "").strip(),
                str(post_text or "").strip(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

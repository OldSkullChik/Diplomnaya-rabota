import random

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_REJECTED,
    ANNOTATION_STATUS_SUBMITTED,
    PROFILE_ROLE_STUDENT,
    SCORE_KIND_AWARD,
    SCORE_KIND_PENALTY,
)
from .forms import AnnotationForm, ReviewForm, SignUpForm, user_is_annotation_admin
from .maintenance import read_maintenance_state
from .models import Annotation, ScoreEvent, SourceRecord, UserProfile
from .permissions import user_can_work, user_is_project_superadmin
from .sampling import CAMPAIGN_POOLS, active_sampling_campaign, filter_for_campaign


RESERVATION_MINUTES = 15
FINAL_ANNOTATION_STATUSES = [ANNOTATION_STATUS_SUBMITTED, ANNOTATION_STATUS_APPROVED]
DELETED_POST_DEFAULTS = {
    "jkh_relevance": "unsure",
    "jkh_topic": "not_jkh",
    "authority_aspect": "not_applicable",
    "sentiment": "neutral",
    "appeal_type": "info",
    "responsible_party": "not_applicable",
    "sarcasm": "unsure",
    "quality": "no_context",
}


def healthz(request):
    db_ok = True
    db_error = ""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        db_ok = False
        db_error = exc.__class__.__name__

    maintenance = read_maintenance_state()
    payload = {
        "status": "ok" if db_ok else "error",
        "database": "ok" if db_ok else "error",
        "maintenance": maintenance["enabled"],
    }
    if db_error:
        payload["database_error"] = db_error
    return JsonResponse(payload, status=200 if db_ok else 503)


def approved_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not user_can_work(request.user):
            return redirect("pending_approval")
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not user_is_annotation_admin(request.user):
            return HttpResponseForbidden("Недостаточно прав.")
        return view_func(request, *args, **kwargs)

    return wrapper


def superadmin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not user_is_project_superadmin(request.user):
            return HttpResponseForbidden("Недостаточно прав.")
        return view_func(request, *args, **kwargs)

    return wrapper


def create_score_event(student, annotation, reviewer, points, reason):
    if not points:
        return None
    return ScoreEvent.objects.create(
        student=student,
        annotation=annotation,
        created_by=reviewer,
        kind=SCORE_KIND_AWARD if points > 0 else SCORE_KIND_PENALTY,
        points=points,
        reason=reason,
    )


def current_streak_for_user(user):
    streak = 0
    reviewed = (
        Annotation.objects.filter(
            student=user,
            is_deleted_post_report=False,
            status__in=[ANNOTATION_STATUS_APPROVED, ANNOTATION_STATUS_REJECTED],
        )
        .order_by("-reviewed_at", "-updated_at")
        .values_list("status", flat=True)
    )
    for status in reviewed:
        if status == ANNOTATION_STATUS_APPROVED:
            streak += 1
            continue
        break
    return streak


def build_leaderboard(limit=10):
    users = (
        User.objects.select_related("profile")
        .filter(Q(profile__is_approved=True) | Q(username="oldskull", is_superuser=True))
        .distinct()
    )
    rows = []
    for user in users:
        score = ScoreEvent.objects.filter(student=user).aggregate(total=Sum("points"))["total"] or 0
        annotation_count = Annotation.objects.filter(student=user, is_deleted_post_report=False).count()
        rows.append(
            {
                "user": user,
                "score": score,
                "annotation_count": annotation_count,
                "streak": current_streak_for_user(user),
                "display_name": getattr(getattr(user, "profile", None), "public_name", "")
                or user.get_full_name()
                or user.username,
            }
        )
    rows.sort(key=lambda item: (-item["score"], -item["annotation_count"], item["user"].username.lower()))
    return rows[:limit] if limit else rows


def records_available_for_user(user, now=None, campaign=None):
    now = now or timezone.now()
    campaign = campaign if campaign is not None else active_sampling_campaign()
    user_annotations = Annotation.objects.filter(record_id=OuterRef("pk"), student=user)
    final_annotations = Annotation.objects.filter(
        record_id=OuterRef("pk"),
        status__in=FINAL_ANNOTATION_STATUSES,
    )
    candidates = (
        SourceRecord.objects.select_for_update()
        .filter(is_active=True)
        .annotate(
            already_annotated_by_user=Exists(user_annotations),
            has_final_annotation=Exists(final_annotations),
        )
        .filter(already_annotated_by_user=False, has_final_annotation=False)
        .filter(Q(reserved_by=user) | Q(reserved_by__isnull=True) | Q(reserved_until__lte=now))
    )
    return filter_for_campaign(candidates, campaign)


def pick_random_record_for_user(user):
    candidates = records_available_for_user(user)
    count = candidates.count()
    if count == 0:
        return None
    return candidates.order_by("id")[random.randrange(count)]


DELETED_POST_PLACEHOLDERS = {"пост удалён", "пост удален", "запись удалена"}


def record_has_deleted_post_placeholder(record):
    post_text = record.post_text.strip().lower().rstrip(".")
    return post_text in DELETED_POST_PLACEHOLDERS


def apply_review_action(annotation, reviewer, action, review_comment=""):
    if annotation.status != ANNOTATION_STATUS_SUBMITTED:
        return False, "Этот ответ уже проверен."

    now = timezone.now()
    record = annotation.record
    record.clear_reservation()

    can_confirm_deleted_post = annotation.is_deleted_post_report or (
        action == "deleted_confirm" and record_has_deleted_post_placeholder(record)
    )

    if can_confirm_deleted_post:
        if action == "deleted_confirm":
            annotation.status = ANNOTATION_STATUS_APPROVED
            annotation.review_comment = review_comment or "Пост действительно удален. Запись исключена из очереди."
            record.is_active = False
            record.save(update_fields=["is_active", "reserved_by", "reserved_until"])
            message = "Отметка о удаленном посте принята. Запись исключена без начисления баллов."
        elif action == "deleted_reject":
            annotation.status = ANNOTATION_STATUS_REJECTED
            annotation.review_comment = review_comment or "Пост не подтвержден как удаленный."
            record.is_active = True
            record.save(update_fields=["is_active", "reserved_by", "reserved_until"])
            create_score_event(annotation.student, annotation, reviewer, -1, annotation.review_comment)
            message = "Отметка отклонена: студенту назначен штраф -1, запись возвращена в очередь."
        else:
            return False, "Для отметки о удаленном посте доступны только решения Да/Нет."
    else:
        if action == "approve":
            annotation.status = ANNOTATION_STATUS_APPROVED
            annotation.review_comment = review_comment or "Принято по шаблону."
            record.save(update_fields=["reserved_by", "reserved_until"])
            create_score_event(annotation.student, annotation, reviewer, 1, annotation.review_comment)
            message = "Ответ принят: студенту начислен +1 балл."
        elif action == "reject":
            annotation.status = ANNOTATION_STATUS_REJECTED
            annotation.review_comment = review_comment or "Отклонено по шаблону."
            record.save(update_fields=["reserved_by", "reserved_until"])
            create_score_event(annotation.student, annotation, reviewer, -2, annotation.review_comment)
            message = "Ответ отправлен в брак: студенту назначен штраф -2, запись возвращена в очередь."
        else:
            return False, "Неизвестное решение проверки."

    annotation.reviewed_by = reviewer
    annotation.reviewed_at = now
    annotation.save(update_fields=["status", "review_comment", "reviewed_by", "reviewed_at", "updated_at"])
    return True, message


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                "Учетная запись создана. Доступ появится после утверждения администратором.",
            )
            return redirect("pending_approval")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def pending_approval(request):
    if user_can_work(request.user):
        return redirect("dashboard")
    return render(request, "annotation/pending_approval.html")


@approved_required
def dashboard(request):
    campaign = active_sampling_campaign()
    assignable_records = filter_for_campaign(SourceRecord.objects.filter(is_active=True), campaign)
    stats = {
        "records": assignable_records.count(),
        "submitted": Annotation.objects.filter(student=request.user).count(),
        "approved": Annotation.objects.filter(student=request.user, status=ANNOTATION_STATUS_APPROVED).count(),
        "rejected": Annotation.objects.filter(student=request.user, status=ANNOTATION_STATUS_REJECTED).count(),
        "pending_review": Annotation.objects.filter(status=ANNOTATION_STATUS_SUBMITTED).count(),
    }
    score = ScoreEvent.objects.filter(student=request.user).aggregate(total=Sum("points"))["total"] or 0
    admin_mode = user_is_annotation_admin(request.user)
    return render(
        request,
        "annotation/dashboard.html",
        {
            "stats": stats,
            "score": score,
            "admin_mode": admin_mode,
            "leaderboard": build_leaderboard(limit=10),
            "campaign": campaign,
        },
    )


@approved_required
@transaction.atomic
def annotate_next(request):
    record = pick_random_record_for_user(request.user)
    if not record:
        return render(request, "annotation/no_records.html")
    record.times_seen += 1
    record.reserve_for(request.user, RESERVATION_MINUTES)
    record.save(update_fields=["times_seen", "reserved_by", "reserved_until"])
    return redirect("annotate_record", record_id=record.id)


@approved_required
def annotate_record(request, record_id):
    campaign = active_sampling_campaign()
    assignable_records = filter_for_campaign(SourceRecord.objects.filter(is_active=True), campaign)
    user_done = Annotation.objects.filter(student=request.user, record__in=assignable_records).count()
    active_records = assignable_records.count()
    remaining = max(active_records - user_done, 0)

    def locked_available_record():
        record = get_object_or_404(
            SourceRecord.objects.select_for_update(),
            id=record_id,
            is_active=True,
        )
        if campaign and record.sampling_pool not in CAMPAIGN_POOLS:
            if record.reserved_by_id == request.user.id:
                record.clear_reservation()
                record.save(update_fields=["reserved_by", "reserved_until"])
            messages.info(request, "Эта запись сейчас не входит в активную выборку для разметки.")
            return None, redirect("annotate_next")
        if Annotation.objects.filter(record=record, student=request.user).exists():
            messages.info(request, "Эта запись уже размечена вами.")
            return None, redirect("annotate_next")
        if Annotation.objects.filter(record=record, status__in=FINAL_ANNOTATION_STATUSES).exists():
            messages.info(request, "Эта запись уже отправлена другим разметчиком.")
            return None, redirect("annotate_next")
        if record.is_reserved_by_other(request.user):
            messages.info(request, "Эта запись сейчас в работе у другого разметчика.")
            return None, redirect("annotate_next")
        if not record.has_active_reservation() or record.reserved_by_id != request.user.id:
            record.reserve_for(request.user, RESERVATION_MINUTES)
            record.save(update_fields=["reserved_by", "reserved_until"])
        return record, None

    if request.method == "POST":
        if request.POST.get("action") == "deleted_post":
            with transaction.atomic():
                record, response = locked_available_record()
                if response:
                    return response
                Annotation.objects.create(
                    record=record,
                    student=request.user,
                    status=ANNOTATION_STATUS_SUBMITTED,
                    is_deleted_post_report=True,
                    student_comment="Пост удален",
                    **DELETED_POST_DEFAULTS,
                )
                record.clear_reservation()
                record.save(update_fields=["reserved_by", "reserved_until"])
                messages.success(request, "Отметка о удаленном посте отправлена на проверку.")
            return redirect("annotate_next")
        form = AnnotationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                record, response = locked_available_record()
                if response:
                    return response
                annotation = form.save(commit=False)
                annotation.record = record
                annotation.student = request.user
                annotation.status = ANNOTATION_STATUS_SUBMITTED
                annotation.save()
                record.clear_reservation()
                record.save(update_fields=["reserved_by", "reserved_until"])
                messages.success(request, "Разметка отправлена на проверку.")
            return redirect("annotate_next")
        with transaction.atomic():
            record, response = locked_available_record()
            if response:
                return response
    else:
        form = AnnotationForm()
        with transaction.atomic():
            record, response = locked_available_record()
            if response:
                return response
    return render(
        request,
        "annotation/annotate.html",
        {
            "record": record,
            "form": form,
            "user_done": user_done,
            "active_records": active_records,
            "remaining": remaining,
        },
    )


@admin_required
def review_queue(request):
    annotations = (
        Annotation.objects.filter(status=ANNOTATION_STATUS_SUBMITTED)
        .select_related("record", "student")
        .annotate(score_events_count=Count("score_events"))
        .order_by("submitted_at")[:100]
    )
    return render(request, "annotation/review_queue.html", {"annotations": annotations})


@admin_required
def participant_list(request):
    profiles = (
        UserProfile.objects.select_related("user", "approved_by")
        .order_by("is_approved", "role", "user__username")
    )
    pending_count = profiles.filter(is_approved=False).count()
    return render(
        request,
        "annotation/participants.html",
        {"profiles": profiles, "pending_count": pending_count},
    )


@admin_required
@transaction.atomic
def approve_participant(request, profile_id):
    if request.method != "POST":
        return redirect("participant_list")
    profile = get_object_or_404(UserProfile.objects.select_related("user"), id=profile_id)
    if not user_is_project_superadmin(request.user) and profile.role != PROFILE_ROLE_STUDENT:
        return HttpResponseForbidden("Администратор разметки может утверждать только студентов.")
    profile.approve(request.user)
    messages.success(request, f"Пользователь {profile.user.username} утвержден.")
    return redirect("participant_list")


@admin_required
@transaction.atomic
def quick_review_annotation(request, annotation_id):
    if request.method != "POST":
        return redirect("review_queue")
    annotation = get_object_or_404(
        Annotation.objects.select_for_update().select_related("record", "student"),
        id=annotation_id,
    )
    success, message = apply_review_action(
        annotation,
        request.user,
        request.POST.get("action", ""),
        request.POST.get("review_comment", ""),
    )
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("review_queue")


@admin_required
@transaction.atomic
def review_annotation(request, annotation_id):
    annotation = get_object_or_404(
        Annotation.objects.select_related("record", "student"),
        id=annotation_id,
    )
    if annotation.is_deleted_post_report and request.method == "POST":
        success, message = apply_review_action(
            annotation,
            request.user,
            request.POST.get("action", ""),
            request.POST.get("review_comment", ""),
        )
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect("review_queue")
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            annotation.status = form.cleaned_data["decision"]
            annotation.review_comment = form.cleaned_data["review_comment"]
            annotation.reviewed_by = request.user
            annotation.reviewed_at = timezone.now()
            annotation.save(update_fields=["status", "review_comment", "reviewed_by", "reviewed_at", "updated_at"])

            award = form.cleaned_data["award_points"]
            penalty = form.cleaned_data["penalty_points"]
            if award:
                ScoreEvent.objects.create(
                    student=annotation.student,
                    annotation=annotation,
                    created_by=request.user,
                    kind=SCORE_KIND_AWARD,
                    points=award,
                    reason=annotation.review_comment,
                )
            if penalty:
                ScoreEvent.objects.create(
                    student=annotation.student,
                    annotation=annotation,
                    created_by=request.user,
                    kind=SCORE_KIND_PENALTY,
                    points=-penalty,
                    reason=annotation.review_comment,
                )
            messages.success(request, "Решение сохранено.")
            return redirect("review_queue")
    else:
        initial = {"decision": ANNOTATION_STATUS_APPROVED, "award_points": 1, "penalty_points": 0}
        form = ReviewForm(initial=initial)
    return render(request, "annotation/review_detail.html", {"annotation": annotation, "form": form})


@superadmin_required
def leaderboard_full(request):
    return render(
        request,
        "annotation/leaderboard.html",
        {"leaderboard": build_leaderboard(limit=None)},
    )


@superadmin_required
@transaction.atomic
def adjust_score(request, user_id):
    if request.method != "POST":
        return redirect("leaderboard_full")
    student = get_object_or_404(User, id=user_id)
    try:
        points = int(request.POST.get("points", "0"))
    except ValueError:
        points = 0
    reason = request.POST.get("reason", "").strip() or "Ручная корректировка суперадмина."
    if points == 0:
        messages.error(request, "Корректировка на 0 баллов не сохраняется.")
        return redirect("leaderboard_full")
    create_score_event(student, None, request.user, points, reason)
    messages.success(request, f"Баллы пользователя {student.username} скорректированы на {points:+d}.")
    return redirect("leaderboard_full")

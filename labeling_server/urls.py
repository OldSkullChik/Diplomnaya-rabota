from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from annotation import api
from annotation import views


urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("api/v1/omsu/manifest/", api.manifest, name="api_omsu_manifest"),
    path("api/v1/omsu/snapshot/", api.snapshot, name="api_omsu_snapshot"),
    path("api/v1/omsu/areas/<slug:slug>/", api.area_detail, name="api_omsu_area_detail"),
    path("api/v1/omsu/latest-comment/", api.latest_comment, name="api_omsu_latest_comment"),
    path("admin/", admin.site.urls),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("pending/", views.pending_approval, name="pending_approval"),
    path("annotate/", views.annotate_next, name="annotate_next"),
    path("annotate/<int:record_id>/", views.annotate_record, name="annotate_record"),
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:annotation_id>/", views.review_annotation, name="review_annotation"),
    path("review/<int:annotation_id>/quick/", views.quick_review_annotation, name="quick_review_annotation"),
    path("participants/", views.participant_list, name="participant_list"),
    path("participants/<int:profile_id>/approve/", views.approve_participant, name="approve_participant"),
    path("leaderboard/", views.leaderboard_full, name="leaderboard_full"),
    path("leaderboard/<int:user_id>/adjust/", views.adjust_score, name="adjust_score"),
]

from .choices import PROFILE_ROLE_ADMIN


PROJECT_SUPERADMIN_USERNAME = "oldskull"


def user_is_project_superadmin(user):
    return bool(
        user.is_authenticated
        and user.is_superuser
        and user.username == PROJECT_SUPERADMIN_USERNAME
    )


def user_is_annotation_admin(user):
    if not user.is_authenticated:
        return False
    if user_is_project_superadmin(user):
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_approved and profile.role == PROFILE_ROLE_ADMIN)


def user_can_work(user):
    if not user.is_authenticated:
        return False
    if user_is_project_superadmin(user):
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_approved)


def project_role_label(user):
    if not user.is_authenticated:
        return ""
    if user_is_project_superadmin(user):
        return "Суперадмин"
    profile = getattr(user, "profile", None)
    if profile and profile.role == PROFILE_ROLE_ADMIN:
        return "Админ"
    if profile:
        return profile.get_role_display()
    return "Пользователь"

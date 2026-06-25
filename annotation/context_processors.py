from .permissions import (
    project_role_label,
    user_is_annotation_admin,
    user_is_project_superadmin,
)


def project_roles(request):
    user = getattr(request, "user", None)
    if user is None:
        return {
            "is_project_superadmin": False,
            "is_annotation_admin": False,
            "project_role_label": "",
        }
    return {
        "is_project_superadmin": user_is_project_superadmin(user),
        "is_annotation_admin": user_is_annotation_admin(user),
        "project_role_label": project_role_label(user),
    }

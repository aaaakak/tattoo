from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    # The custom admin site is installed via AdminConfig.default_site in
    # apps/core/admin_config.py -- see the comment there for why that mechanism is used
    # rather than reassigning admin.site in ready().

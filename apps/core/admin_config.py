"""
AdminConfig that installs the custom admin site.

This module is imported during INSTALLED_APPS resolution, i.e. extremely early, so it
must not import models or admin modules — only the site class, which imports nothing
beyond django.contrib.admin.
"""

from django.contrib.admin.apps import AdminConfig


class TattoWebAdminConfig(AdminConfig):
    """
    Points Django's admin autodiscovery at our site.

    Mechanism: AdminConfig.ready() calls admin.autodiscover(ignore=None) and
    autodiscover() instantiates `admin.site` from `self.default_site`. Setting
    default_site here means our TattoWebAdminSite is created and populated by Django's
    own machinery, in Django's own order.

    This replaces an earlier approach that reassigned `admin.site` inside
    CoreConfig.ready(). That ran *after* the admin modules had already been imported and
    decorated against the original site, so the custom site ended up with zero
    registrations -- a silent failure that only surfaced when the admin index rendered
    an empty model list.
    """

    default_site = "apps.core.admin_site.TattoWebAdminSite"

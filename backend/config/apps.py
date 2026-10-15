from django.contrib.admin.apps import AdminConfig


class EveAdminConfig(AdminConfig):
    default_site = 'config.admin_site.EveAdminSite'

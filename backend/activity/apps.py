from django.apps import AppConfig


class ActivityConfig(AppConfig):
    name = 'activity'
    verbose_name = '활동·변경 로그'

    def ready(self):
        from . import tracking
        tracking.install()

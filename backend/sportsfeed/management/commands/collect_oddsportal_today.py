import os
from django.conf import settings
from django.db import connections
from django.core.management.base import BaseCommand
from sportsfeed.oddsportal_jobs import run_job


class Command(BaseCommand):
    help = '관리자가 요청한 OddsPortal 오늘 전체 종목 수집 작업을 실행합니다.'
    def add_arguments(self, parser): parser.add_argument('job_id',type=int)
    def handle(self,*args,**options):
        # A detached worker must use the same database as its launching server.
        database=os.environ.get('EVEPREVIEW_JOB_DATABASE')
        if database:
            connections['default'].close()
            settings.DATABASES['default']['NAME']=database
            connections['default'].settings_dict['NAME']=database
        run_job(options['job_id'])

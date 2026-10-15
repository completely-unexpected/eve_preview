import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections
from sportsfeed.harvester import run_job


class Command(BaseCommand):
    help='관리자가 요청한 별도 OddsHarvester 수집 작업을 실행합니다.'
    def add_arguments(self,parser): parser.add_argument('job_id',type=int)
    def handle(self,*args,**options):
        database=os.environ.get('EVEPREVIEW_JOB_DATABASE')
        if database:
            connections['default'].close()
            settings.DATABASES['default']['NAME']=database
            connections['default'].settings_dict['NAME']=database
        run_job(options['job_id'])

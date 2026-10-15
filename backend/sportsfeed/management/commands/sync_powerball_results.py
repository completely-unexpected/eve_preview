import time
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from sportsfeed.models import DemoLeg, PowerballSync
from sportsfeed.powerball_results import sync_results

class Command(BaseCommand):
    help='공식 엔트리 공개 결과를 저장하고 시뮬레이션 접수를 정산합니다.'
    def add_arguments(self, parser): parser.add_argument('--watch', action='store_true')
    def handle(self,*args,**options):
        while True:
            try:
                state=PowerballSync.objects.filter(pk=1).first()
                pending=DemoLeg.objects.filter(slip__source='powerball', result='pending').exists()
                due=not state or not state.fetched_at or timezone.now()-state.fetched_at>=timedelta(seconds=30 if pending else 300)
                if due or not options['watch']: self.stdout.write(str(sync_results()))
            except Exception as exc:
                if not options['watch']: raise CommandError(str(exc))
                self.stderr.write(str(exc))
            if not options['watch']: return
            time.sleep(30)

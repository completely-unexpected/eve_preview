import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from django.db import OperationalError
from sportsfeed.models import FeedSnapshot
from sportsfeed.portal_bridge import SPORTS,eligible,apply_results


class Command(BaseCommand):
    help='OddsPortal 공개 결과와 기존 스포츠 경기를 대조하여 종료 상태를 반영합니다. 유료 API를 호출하지 않습니다.'
    def add_arguments(self,parser):
        parser.add_argument('--watch',action='store_true')
        parser.add_argument('--interval',type=int,default=900)
        parser.add_argument('--input-file')
    def handle(self,*args,**options):
        if options['interval']<300: raise CommandError('조회 간격은 300초 이상이어야 합니다.')
        from sportsfeed.collector_control import is_paused
        while True:
            if is_paused():
                if not options['watch']: raise CommandError('결과 수집이 중지되어 있습니다.')
                time.sleep(2);continue
            state=FeedSnapshot.objects.filter(pk=1).first()
            events=[event for event in state.payload.get('items',[]) if eligible(event,timezone.now())] if state else []
            sports=sorted({SPORTS[event['group']] for event in events if event.get('group') in SPORTS})
            if not sports:
                self.stdout.write('No unresolved past events.')
                if not options['watch']: return
                time.sleep(options['interval']);continue
            reports=[];rows=[]
            if options['input_file']:
                content=Path(options['input_file']).read_bytes()
                text=content.decode('utf-16') if content.startswith((b'\xff\xfe',b'\xfe\xff')) else content.decode('utf-8-sig')
                lines=text.splitlines()
            else:
                node=shutil.which('node') or str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'nodejs/node.exe')
                env={**os.environ,'ODDSPORTAL_RESULT_SPORTS':json.dumps(sports)}
                process=subprocess.Popen([node,str(settings.BASE_DIR.parent/'tools/oddsportal/results.cjs')],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',env=env)
                lines=process.stdout
            for line in lines:
                try: event=json.loads(line)
                except ValueError: continue
                if event.get('type')=='page':
                    rows.extend(event.get('items',[]));reports.append(event.get('report',{}))
                    self.stdout.write(json.dumps(event.get('report',{}),ensure_ascii=True))
                elif event.get('type')=='fatal': self.stderr.write(event.get('error','Collection failed'))
            if not options['input_file']: process.wait()
            if is_paused():
                self.stdout.write('Paused; no result changes applied.')
            else:
                try:
                    report=apply_results(rows);self.stdout.write(json.dumps(report))
                except OperationalError:
                    if not options['watch']: raise CommandError('저장 중입니다. 잠시 후 다시 실행해 주세요.')
                    self.stderr.write('Database busy; will retry next interval.')
            if not options['watch'] or options['input_file']: return
            time.sleep(options['interval'])

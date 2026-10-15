import json
import os
import shutil
import subprocess
import time
from urllib.parse import urlsplit
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from sportsfeed.models import OddsPortalSnapshot


class Command(BaseCommand):
    help = "OddsPortal 공개 웹페이지의 경기·표시 배당·결과를 저장합니다."
    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=int, default=60)
    def handle(self, *args, **options):
        if options["interval"] < 30:
            raise CommandError("조회 간격은 30초 이상으로 설정해 주세요.")
        node = shutil.which("node") or str(Path(os.environ.get("ProgramFiles", "C:/Program Files"))/"nodejs/node.exe")
        script = settings.BASE_DIR.parent/"tools/oddsportal/collect.cjs"
        while True:
            from sportsfeed.collector_control import is_paused
            if is_paused():
                if not options["watch"]: raise CommandError("결과 자동 수집이 중지되어 있습니다.")
                time.sleep(2)
                continue
            from sportsfeed.models import OddsPortalCollectionJob
            if OddsPortalCollectionJob.objects.filter(active_key='today').exists():
                if not options['watch']: raise CommandError('오늘 경기 전체 수집이 진행 중입니다.')
                time.sleep(options['interval'])
                continue
            state,_ = OddsPortalSnapshot.objects.get_or_create(pk=1)
            try:
                env=os.environ.copy()
                active_pages=set()
                for item in state.payload.get('items',[]):
                    if item.get('status') in ('finished','cancelled'): continue
                    page=item.get('sourcePage','')
                    parsed=urlsplit(page)
                    if parsed.scheme=='https' and parsed.netloc=='www.oddsportal.com' and not parsed.query:
                        active_pages.add(page)
                if active_pages and 'ODDSPORTAL_PAGES' not in env:
                    env['ODDSPORTAL_PAGES']=json.dumps(sorted(active_pages)[:50])
                result = subprocess.run([node,str(script)],capture_output=True,text=True,encoding="utf-8",timeout=max(180,len(active_pages)*90),env=env)
                if result.returncode:
                    raise ValueError((result.stderr[:350] + result.stderr[-350:]) or "수집 프로세스 실패")
                if is_paused():
                    continue
                data=json.loads(result.stdout)
                items=data.get("items")
                if not isinstance(items,list) or not items or len(items)>10000:
                    raise ValueError("유효한 경기 목록이 없습니다.")
                old={i["id"]:i for i in state.payload.get("items",[])}
                for item in items:
                    if not all(isinstance(item.get(k),str) and item[k] for k in ("id","home","away","url")):
                        raise ValueError("경기 식별 정보가 올바르지 않습니다.")
                    previous=old.get(item["id"])
                    if previous and (previous["home"]!=item["home"] or previous["away"]!=item["away"]):
                        raise ValueError("경기 식별 정보가 충돌했습니다.")
                    if previous and previous.get('status')=='finished' and item.get('status')!='finished':
                        continue
                    old[item["id"]]=item
                # Bound retained history; current observations are kept at the end.
                data["items"]=list(old.values())[-10000:]
                state.payload=data
                state.fetched_at=timezone.now()
                state.last_error=""
                state.save()
                self.stdout.write(f"OddsPortal: {len(items)}경기 수집 / {len(data['items'])}경기 보관")
            except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
                state.last_error=str(exc)[:500]
                state.save(update_fields=["last_error"])
                if not options["watch"]: raise CommandError(state.last_error)
                self.stderr.write(state.last_error)
            if not options["watch"]: break
            time.sleep(options["interval"])

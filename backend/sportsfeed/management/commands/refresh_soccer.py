from django.core.management.base import BaseCommand, CommandError
from sportsfeed.refresh import refresh_soccer
from sportsfeed.services import ProviderError

class Command(BaseCommand):
    help = '축구 기본 배당 및 최근 경기 결과를 크레딧 한도 내에서 갱신합니다.'
    def handle(self, *args, **options):
        try: snapshot=refresh_soccer(progress=self.stdout.write)
        except ProviderError as exc: raise CommandError(str(exc))
        r=snapshot.payload.get('lastRefresh', {})
        self.stdout.write(f"Updated leagues: {len(r.get('leagues', []))}; score leagues: {len(r.get('scoreLeagues', []))}; errors: {len(r.get('errors', []))}; credits remaining: {snapshot.payload.get('remainingCredits')}")

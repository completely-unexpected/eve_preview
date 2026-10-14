from django.core.management.base import BaseCommand, CommandError
from sportsfeed.collector import collect
from sportsfeed.services import ProviderError
class Command(BaseCommand):
    help = "Fetch all supported event lists, EU main odds and available scores; consumes API credits."
    def add_arguments(self, parser): parser.add_argument("--force", action="store_true")
    def handle(self, *args, **options):
        try: snapshot = collect(force=options["force"], progress=self.stdout.write)
        except ProviderError as exc: raise CommandError(str(exc)) from None
        data = snapshot.payload
        self.stdout.write(f"RESULT games={len(data.get('items', []))} leagues={len(data.get('completedLeagues', []))} remaining={data.get('remainingCredits')} complete={data.get('complete')}")

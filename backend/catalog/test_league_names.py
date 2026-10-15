from django.test import SimpleTestCase
from .league_names import league_name, localize_events, localize_leagues
from .odds import categorize


class LeagueNamesTests(SimpleTestCase):
    def test_translation_fallback_and_identifiers(self):
        self.assertEqual(league_name('EPL'), '잉글랜드 프리미어리그')
        self.assertEqual(league_name('Europe / Champions League'), '유럽 / 챔피언스리그')
        self.assertEqual(league_name('Unlisted Cup'), 'Unlisted Cup')
        original=[{'id':'a','league':'KBO','leagueKey':'baseball_kbo'}]
        translated=localize_events(original)
        self.assertEqual(translated[0]['league'], '한국 프로야구')
        self.assertEqual(translated[0]['leagueKey'], 'baseball_kbo')
        self.assertEqual(original[0]['league'], 'KBO')
        self.assertEqual(localize_leagues([{'key':'soccer_epl','title':'EPL'}])[0]['title'], '잉글랜드 프리미어리그')
        raw=[{'url':'https://www.oddsportal.com/football/h2h/a/b/#12345678','leagueText':'Football / Europe / Champions League'}]
        translated=categorize(raw,'oddsportal')
        self.assertEqual(translated[0]['league'], '유럽 / 챔피언스리그')
        self.assertEqual(translated[0]['leagueKey'], categorize(raw,'oddsportal')[0]['leagueKey'])

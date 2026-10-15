from datetime import timedelta
from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.utils import timezone
from .models import ManualOdds, Game
from .odds import choices, apply_prices
from sportsfeed.models import FeedSnapshot, OddsPortalSnapshot


class ManualOddsTests(TestCase):
    def test_game_results_show_powerball_market_outcomes(self):
        from sportsfeed.models import PowerballResult
        PowerballResult.objects.create(day='2026-10-15',round_number=1,global_round=999001,balls=[26,20,12,28,2],powerball=3)
        Game.objects.filter(slug='powerball').update(is_published=False)
        for suffix in ('?status=results&source=powerball','?status=results'):
            response=self.client.get(self.url+suffix)
            self.assertEqual(response.status_code,200)
            for label in ('일반볼 5개','일반볼 합계','일반볼 홀/짝','일반볼 대/중/소','파워볼 홀/짝','파워볼 언더/오버','대 (81~130)','언더 (0~4)'):
                self.assertContains(response,label)
            self.assertContains(response,'>88</td>')
            self.assertContains(response,'class="pb-result-choice winner"',count=4)
            self.assertContains(response,'<strong>1.95</strong>',count=6,html=True)
            self.assertContains(response,'<strong>2.85</strong>',count=2,html=True)
            self.assertNotContains(response,'<button type="button" class="edit-odd"')

    def test_sport_then_league_filters(self):
        from copy import deepcopy
        soccer=deepcopy(self.event);soccer.update(id='soccer',group='Soccer',league='Premier League',leagueKey='soccer_epl')
        baseball=deepcopy(self.event);baseball.update(id='baseball',group='Baseball',league='MLB',leagueKey='baseball_mlb')
        self.state.payload={'items':[soccer,baseball]};self.state.save()
        response=self.client.get(self.url+'?source=sports&sport=football')
        self.assertEqual([row['event']['id'] for row in response.context['page']], ['soccer'])
        self.assertEqual(response.context['leagues'], [('soccer_epl','프리미어리그')])
        response=self.client.get(self.url+'?source=sports&sport=baseball&league=baseball_mlb')
        self.assertEqual([row['event']['id'] for row in response.context['page']], ['baseball'])
        baseball['completed']=True;self.state.payload={'items':[soccer,baseball]};self.state.save()
        self.assertEqual(self.client.get(self.url+'?sport=baseball').context['total'],0)
        self.assertEqual(self.client.get(self.url+'?status=results&sport=baseball').context['total'],1)

    def test_inline_save_and_finished_games_are_locked(self):
        response = self.client.post(self.edit, {'inline':'1', 'key':self.key, 'value':'3.5'})
        self.assertEqual(response.json()['price'], '3.50')
        self.assertContains(self.client.get(self.url), 'class="edit-odd"')
        self.event.update(status='finished', completed=True, scores=[{'score':'0'}, {'score':'0'}])
        self.state.payload={'items':[self.event]}; self.state.save()
        active=self.client.get(self.url)
        self.assertNotContains(active, '>Home</td>')
        results=self.client.get(self.url+'?status=results')
        self.assertContains(results, '>Home</td>')
        self.assertContains(results, '0 : 0')
        self.assertNotContains(results, '<button type="button" class="edit-odd"')
        self.assertNotContains(results, '<th>관리</th>')
        self.assertEqual(self.client.post(self.edit, {'inline':'1','key':self.key,'value':'4'}).status_code, 409)
        self.assertEqual(self.client.post(self.edit, {'odd_'+self.key:'4'}).status_code, 409)
        self.assertEqual(ManualOdds.objects.get(source='sports',event_id='event1').prices[self.key], '3.5000')

    def test_winner_highlight_uses_team_scores_and_keeps_draw_neutral(self):
        from .odds import row_display
        self.event.update(completed=True, scores=[{'name':'Away','score':'3'},{'name':'Home','score':'5'}])
        self.assertEqual(row_display(self.event,'sports')['winner'], 'home')
        self.event['scores']=[{'name':'Home','score':'0'},{'name':'Away','score':'0'}]
        self.assertEqual(row_display(self.event,'sports')['winner'], '')
        self.assertEqual(row_display({'home':'A','away':'B','status':'finished','scores':[1,2]},'oddsportal')['winner'], 'away')

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='odds_admin', password=None)
        self.client.force_login(self.admin)
        self.event = {'id': 'event1', 'home': 'Home', 'away': 'Away', 'league': 'League', 'status': 'scheduled',
            'startsAt': (timezone.now()+timedelta(days=1)).isoformat(),
            'bookmakers': [{'key': 'book', 'title': 'Book', 'markets': [{'key': 'h2h', 'outcomes': [
                {'name': 'Home', 'price': '2.0000', 'point': None, 'description': ''}]}]}]}
        self.state = FeedSnapshot.objects.create(payload={'items': [self.event]})
        OddsPortalSnapshot.objects.create(payload={'items': [{'id': 'op1', 'home': 'One', 'away': 'Two', 'odds': ['1.5', '2.5']}]}, fetched_at=timezone.now())
        self.url = '/admin/catalog/game/odds/'
        self.edit = self.url+'?'+urlencode({'source': 'sports', 'event': 'event1'})
        self.key = next(choices(self.event, 'sports'))[0]

    def test_edit_persists_across_source_refresh_and_reset(self):
        response = self.client.get(self.url)
        self.assertContains(response, '>One</td>')
        self.assertContains(response, '>Two</td>')
        self.assertEqual(self.client.post(self.edit, {'odd_'+self.key: '3.25'}).status_code, 302)
        def price():
            return self.client.get('/api/sports/board/').json()['items'][0]['bookmakers'][0]['markets'][0]['outcomes'][0]['price']
        self.assertEqual(price(), '3.2500')
        self.event['bookmakers'][0]['markets'][0]['outcomes'][0]['price'] = '1.8000'
        self.state.payload = {'items': [self.event]}; self.state.save()
        self.assertEqual(price(), '3.2500')
        self.client.post(self.edit, {})
        self.assertEqual(price(), '1.8000')

    def test_invalid_and_permission_denied(self):
        for value in ('NaN', '-1', '1', '1000001', '2.12345'):
            self.assertEqual(self.client.post(self.edit, {'odd_'+self.key: value}).status_code, 200)
            self.assertFalse(ManualOdds.objects.exists())
        viewer = get_user_model().objects.create_user(username='odds_viewer', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_game'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.edit).status_code, 200)
        self.assertEqual(self.client.post(self.edit, {'odd_'+self.key:'2.5'}).status_code, 403)
        client = Client(enforce_csrf_checks=True); client.force_login(self.admin)
        self.assertEqual(client.post(self.edit, {}).status_code, 403)

    def test_op_and_powerball_prices(self):
        url = self.url+'?source=oddsportal&event=op1'
        self.client.post(url, {'odd_0':'4.5'})
        self.assertEqual(self.client.get('/api/sports/oddsportal/').json()['items'][0]['odds'], ['4.5000','2.5'])
        Game.objects.update_or_create(slug='powerball', defaults={'name':'Powerball','category':'ball','is_published':True})
        from sportsfeed.powerball import current_board
        event = current_board(manual=False)['items'][0]
        key = next(choices(event, 'powerball'))[0]
        ManualOdds.objects.create(source='powerball', event_id=event['id'], prices={key:'2.5000'}, updated_by=self.admin)
        self.assertEqual(current_board()['items'][0]['bookmakers'][0]['markets'][0]['outcomes'][0]['price'], '2.5000')

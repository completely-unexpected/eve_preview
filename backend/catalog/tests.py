from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Game

class CatalogTests(TestCase):
    def setUp(self):
        Game.objects.all().delete()
        self.visible=Game.objects.create(name='게임',slug='public-game',category='ball',is_published=True,sort_order=2)
        self.first=Game.objects.create(name='먼저',slug='first',category='cards',is_published=True,sort_order=1)
        self.hidden=Game.objects.create(name='비공개',slug='hidden',category='ladder')
    def test_order_and_only_published(self):
        response=self.client.get('/api/games/')
        self.assertEqual([g['slug'] for g in response.json()['items']],['first','public-game'])
        self.assertIn('no-store',response['Cache-Control'])
    def test_detail_hides_unpublished_and_missing(self):
        self.assertEqual(self.client.get('/api/games/public-game/').json()['game']['name'],'게임')
        for slug in ('hidden','missing'):
            self.assertEqual(self.client.get('/api/games/'+slug+'/').status_code,404)
        self.visible.is_published=False
        self.visible.save()
        self.assertEqual(self.client.get('/api/games/public-game/').status_code,404)
    def test_empty_and_read_only(self):
        for url in ('/api/games/','/api/games/public-game/'):
            self.assertEqual(self.client.post(url,{'name':'위조'}).status_code,405)
        Game.objects.all().delete()
        self.assertEqual(self.client.get('/api/games/').json()['items'],[])
    def test_admin_create_edit_and_permissions(self):
        member=get_user_model().objects.create_user(username='member')
        self.client.force_login(member)
        self.assertEqual(self.client.get('/admin/catalog/game/').status_code,302)
        admin=get_user_model().objects.create_superuser(username='operator',password='Orbit!2026-Catalog')
        self.client.force_login(admin)
        data={'name':'새 게임','slug':'new-game','english_name':'NEW GAME','category':'sports','symbol':'⚽','description':'게임 안내','sort_order':'0','is_published':'on','_save':'저장'}
        self.assertEqual(self.client.post('/admin/catalog/game/add/',data).status_code,302)
        game=Game.objects.get(slug='new-game')
        data.update(name='수정 게임',slug='forged',category='cards')
        self.assertEqual(self.client.post(f'/admin/catalog/game/{game.pk}/change/',data).status_code,302)
        game.refresh_from_db()
        self.assertEqual(game.name,'수정 게임')
        self.assertEqual(game.slug,'new-game')
        self.assertEqual(game.category,'cards')
    def test_admin_rejects_bad_category_and_duplicate_slug(self):
        operator=get_user_model().objects.create_superuser(username='operator',password='Orbit!2026-Catalog')
        self.client.force_login(operator)
        data={'name':'게임','slug':'public-game','category':'invalid','symbol':'🎮','sort_order':'0','_save':'저장'}
        response=self.client.post('/admin/catalog/game/add/',data)
        self.assertEqual(response.status_code,200)
        self.assertIn('slug',response.context['adminform'].form.errors)
        self.assertIn('category',response.context['adminform'].form.errors)

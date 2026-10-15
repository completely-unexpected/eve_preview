from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase


class AdminNavigationTests(TestCase):
    def test_registration_engines_and_game_management_groups(self):
        user=get_user_model().objects.create_superuser(username='engine_nav_admin')
        self.client.force_login(user)
        response=self.client.get('/admin/')
        self.assertContains(response,'<summary>등록엔진</summary>',html=True)
        self.assertNotContains(response,'<summary>경기 API</summary>',html=True)
        apps=response.context['available_apps']
        engine=next(app for app in apps if app['app_label']=='sportsfeed')
        self.assertEqual([group['name'] for group in engine['menu_groups']],['OddsHarvester','OddsParsing','The Odds API','Inplay'])
        self.assertNotIn('DemoSlip',{model['object_name'] for model in engine['models']})
        games=next(app for app in apps if app['app_label']=='catalog')
        self.assertTrue({'MatchOdds','MatchResults','DemoLeg','DemoSlip'}<={model['object_name'] for model in games['models']})

    def test_engine_submenus_preserve_permissions(self):
        user=get_user_model().objects.create_user(username='engine_viewer',is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_feedsnapshot'))
        self.client.force_login(user)
        engine=next(app for app in self.client.get('/admin/').context['available_apps'] if app['app_label']=='sportsfeed')
        self.assertEqual([group['name'] for group in engine['menu_groups']],['The Odds API'])

    def test_top_navigation_groups_support(self):
        user = get_user_model().objects.create_superuser(username='nav_admin', password=None)
        self.client.force_login(user)
        response = self.client.get('/admin/')
        self.assertContains(response, 'class="admin-top-menu"')
        self.assertContains(response, '<summary>고객센터</summary>', html=True)
        self.assertNotContains(response, 'id="nav-sidebar"')
        apps = response.context['available_apps']
        support = next(app for app in apps if app['app_label'] == 'customer_support')
        self.assertTrue({'Inquiry', 'Post', 'Notice'} <= {model['object_name'] for model in support['models']})
        self.assertFalse({'notices', 'inquiries', 'board'} & {app['app_label'] for app in apps})
        self.assertEqual(self.client.get('/admin/board/post/').status_code, 200)

    def test_support_menu_respects_permissions(self):
        user = get_user_model().objects.create_user(username='nav_viewer', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_inquiry'))
        self.client.force_login(user)
        response = self.client.get('/admin/')
        support = next(app for app in response.context['available_apps'] if app['app_label'] == 'customer_support')
        self.assertEqual([model['object_name'] for model in support['models']], ['Inquiry'])

from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Event
class EventTests(TestCase):
    def setUp(self):
        Event.objects.all().delete()
        self.public=Event.objects.create(title='공개',summary='요약',body='첫 줄\n둘째 줄',is_published=True,sort_order=2)
        self.first=Event.objects.create(title='먼저',summary='요약',body='내용',is_published=True,sort_order=1)
        self.draft=Event.objects.create(title='숨김',summary='요약',body='내용')
    def test_order_and_drafts_hidden(self):
        response=self.client.get('/api/events/')
        self.assertEqual([e['id'] for e in response.json()['items']],[self.first.pk,self.public.pk])
        self.assertIn('no-store',response['Cache-Control'])
        for pk in (self.draft.pk,99999):
            self.assertEqual(self.client.get(f'/api/events/{pk}/').status_code,404)
    def test_detail_and_unpublishing(self):
        self.assertEqual(self.client.get(f'/api/events/{self.public.pk}/').json()['event']['body'],'첫 줄\n둘째 줄')
        self.public.is_published=False
        self.public.save()
        self.assertEqual(self.client.get(f'/api/events/{self.public.pk}/').status_code,404)
    def test_empty_and_read_only(self):
        for url in ('/api/events/',f'/api/events/{self.public.pk}/'):
            self.assertEqual(self.client.post(url,{}).status_code,405)
        Event.objects.all().delete()
        self.assertEqual(self.client.get('/api/events/').json()['items'],[])
    def test_admin_permissions_create_and_edit(self):
        member=get_user_model().objects.create_user(username='member')
        self.client.force_login(member)
        self.assertEqual(self.client.get('/admin/events/event/').status_code,302)
        operator=get_user_model().objects.create_superuser(username='operator',password='Orbit!2026-Events')
        self.client.force_login(operator)
        data={'title':'새 이벤트','summary':'요약','body':'내용','symbol':'🎁','tag':'NEW','sort_order':'0','is_published':'on','_save':'저장'}
        self.assertEqual(self.client.post('/admin/events/event/add/',data).status_code,302)
        event=Event.objects.get(title='새 이벤트')
        data.update(title='수정 이벤트',body='수정 내용')
        self.assertEqual(self.client.post(f'/admin/events/event/{event.pk}/change/',data).status_code,302)
        self.assertEqual(self.client.get(f'/api/events/{event.pk}/').json()['event']['body'],'수정 내용')

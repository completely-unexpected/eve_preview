from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from notices.models import Notice
from .models import Post
class BoardTests(TestCase):
    def setUp(self):
        self.member=get_user_model().objects.create_user(username='member',nickname='회원 닉네임')
        self.post=Post.objects.create(author=self.member,title='공개 글',body='첫 줄\n둘째 줄')
        self.hidden=Post.objects.create(author=self.member,title='숨긴 글',body='비공개',is_published=False)
        self.pinned=Notice.objects.create(title='고정 공지',body='내용',is_published=True,is_pinned=True)
        Notice.objects.create(title='미게시 고정',body='내용',is_pinned=True)
        Notice.objects.create(title='일반 공지',body='내용',is_published=True)
    def test_public_reads_and_only_published_pinned_notices(self):
        response=self.client.get('/api/board/')
        self.assertEqual([n['id'] for n in response.json()['pinnedNotices']],[self.pinned.pk])
        self.assertEqual([p['id'] for p in response.json()['items']],[self.post.pk])
        self.assertEqual(response.json()['items'][0]['author'],'회원 닉네임')
        self.assertNotIn('member',response.content.decode())
        self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.client.get(f'/api/board/{self.post.pk}/').json()['post']['body'],'첫 줄\n둘째 줄')
        self.assertEqual(self.client.get(f'/api/board/{self.hidden.pk}/').status_code,404)
    def test_member_create_cannot_forge_author_or_visibility(self):
        other=get_user_model().objects.create_user(username='other')
        self.client.force_login(self.member)
        response=self.client.post('/api/board/',{'title':' 新 글 ', 'body':' 내용 ', 'author':other.pk,'is_published':'false'})
        self.assertEqual(response.status_code,201)
        post=Post.objects.get(pk=response.json()['post']['id'])
        self.assertEqual(post.author,self.member)
        self.assertTrue(post.is_published)
        self.assertEqual(post.body,'내용')
    def test_write_requires_active_login_and_csrf(self):
        self.assertEqual(self.client.post('/api/board/',{'title':'글','body':'내용'}).status_code,401)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.member)
        self.assertEqual(strict.post('/api/board/',{'title':'글','body':'내용'}).status_code,403)
        token=strict.get('/api/accounts/session/').json()['csrfToken']
        self.assertEqual(strict.post('/api/board/',{'title':'글','body':'내용'},HTTP_X_CSRFTOKEN=token).status_code,201)
        self.member.account_status='suspended';self.member.save()
        self.client.force_login(self.member)
        self.assertEqual(self.client.post('/api/board/',{'title':'글','body':'내용'}).status_code,401)
    def test_validation_and_pagination(self):
        self.client.force_login(self.member)
        for data in ({'title':' ','body':'내용'},{'title':'글','body':' '},{'title':'가'*201,'body':'내용'},{'title':'글','body':'가'*10001}):
            self.assertEqual(self.client.post('/api/board/',data).status_code,400)
        Post.objects.bulk_create([Post(author=self.member,title=str(i),body='내용') for i in range(22)])
        self.assertEqual(len(self.client.get('/api/board/').json()['items']),20)
        self.assertEqual(len(self.client.get('/api/board/?page=2').json()['items']),3)
        self.assertEqual(len(self.client.get('/api/board/?page=2').json()['pinnedNotices']),1)
    def test_admin_hide_and_pin_changes(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get('/admin/board/post/').status_code,302)
        operator=get_user_model().objects.create_superuser(username='operator',password='Orbit!2026-Board')
        self.client.force_login(operator)
        response=self.client.post(f'/admin/board/post/{self.post.pk}/change/',{'title':'공개 글','body':'내용','_save':'저장'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get(f'/api/board/{self.post.pk}/').status_code,404)
        self.pinned.is_pinned=False;self.pinned.save()
        self.assertEqual(self.client.get('/api/board/').json()['pinnedNotices'],[])

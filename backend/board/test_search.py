from django.test import TestCase
from .models import Post
from notices.models import Notice
class BoardSearchTests(TestCase):
    def setUp(self):
        Post.objects.bulk_create([Post(title=f'검색 대상 {i}',body='본문') for i in range(23)])
        self.body_match=Post.objects.create(title='다른 제목',body='내용의 검색 대상')
        Post.objects.create(title='검색 대상 비공개',body='내용',is_published=False)
        Post.objects.create(title='관련 없음',body='일반 내용')
        self.notice=Notice.objects.create(title='고정 안내',body='공지',is_published=True,is_pinned=True)
    def test_title_body_search_and_paginated_stable_numbers(self):
        first=self.client.get('/api/board/',{'q':' 검색 대상 '}).json()
        second=self.client.get('/api/board/',{'q':'검색 대상','page':2}).json()
        self.assertEqual(first['query'],'검색 대상')
        self.assertEqual(first['count'],24)
        self.assertEqual(len(first['items']),20)
        self.assertEqual(len(second['items']),4)
        self.assertEqual(first['items'][0]['id'],self.body_match.pk)
        self.assertFalse(set(p['id'] for p in first['items'])&set(p['id'] for p in second['items']))
        self.assertEqual(second['pinnedNotices'][0]['id'],self.notice.pk)
    def test_no_match_and_clear_search(self):
        self.assertEqual(self.client.get('/api/board/',{'q':'없는 검색어'}).json()['count'],0)
        self.assertEqual(self.client.get('/api/board/').json()['count'],25)
    def test_special_text_is_literal_search(self):
        self.assertEqual(self.client.get('/api/board/',{'q':"' OR 1=1 --"}).json()['items'],[])

from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Notice

class NoticeTests(TestCase):
    def setUp(self):
        self.draft = Notice.objects.create(title="비공개", body="숨긴 내용")
        self.public = Notice.objects.create(title="공지", body="첫 줄\n둘째 줄", is_published=True)
        self.pinned = Notice.objects.create(title="고정 공지", body="내용", is_published=True, is_pinned=True)

    def test_public_list_order_and_hidden_drafts(self):
        response = self.client.get("/api/notices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([n["id"] for n in response.json()["items"]], [self.pinned.pk, self.public.pk])
        self.assertIn("no-store", response["Cache-Control"])

    def test_detail_and_unpublished_or_missing_not_found(self):
        self.assertEqual(self.client.get(f"/api/notices/{self.public.pk}/").json()["notice"]["body"], "첫 줄\n둘째 줄")
        for pk in (self.draft.pk, 999999):
            self.assertEqual(self.client.get(f"/api/notices/{pk}/").status_code, 404)
        self.public.is_published = False
        self.public.save()
        self.assertEqual(self.client.get(f"/api/notices/{self.public.pk}/").status_code, 404)

    def test_empty_list_and_pagination(self):
        Notice.objects.all().delete()
        self.assertEqual(self.client.get("/api/notices/").json()["items"], [])
        Notice.objects.bulk_create([Notice(title=str(i), body="내용", is_published=True) for i in range(25)])
        self.assertEqual(len(self.client.get("/api/notices/").json()["items"]), 20)
        self.assertEqual(len(self.client.get("/api/notices/?page=2").json()["items"]), 5)

    def test_public_api_read_only(self):
        for path in ("/api/notices/", f"/api/notices/{self.public.pk}/"):
            self.assertEqual(self.client.post(path, {"title": "변경"}).status_code, 405)

    def test_admin_permissions_and_create(self):
        member = get_user_model().objects.create_user(username="member")
        self.client.force_login(member)
        self.assertEqual(self.client.get("/admin/notices/notice/").status_code, 302)
        operator = get_user_model().objects.create_superuser(username="operator", password="Orbit!2026-Notices")
        self.client.force_login(operator)
        self.assertEqual(self.client.get("/admin/notices/notice/").status_code, 200)
        self.assertEqual(self.client.post("/admin/notices/notice/add/", {"title":"새 공지", "body":"새 내용", "is_published":"on", "_save":"저장"}).status_code, 302)
        self.assertTrue(Notice.objects.filter(title="새 공지", is_published=True).exists())

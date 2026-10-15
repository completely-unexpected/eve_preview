from django.test import TestCase, Client
from .models import User, PartnerAccount


class PartnerAdminTests(TestCase):
    def setUp(self):
        self.partner=PartnerAccount(username="partner",name="협력사")
        self.partner.set_password("Orbit!Partner-2026")
        self.partner.save()

    def test_member_login_does_not_grant_partner_access(self):
        user=User.objects.create_user(username="normal",password="Orbit!Partner-2026")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/partner-admin/").status_code,302)
        self.assertEqual(self.client.get("/api/accounts/partner/members/").status_code,401)
        self.assertEqual(self.client.post("/partner-admin/login/",{"username":"normal","password":"Orbit!Partner-2026"}).status_code,400)

    def test_csrf_logout_and_cache(self):
        c=Client(enforce_csrf_checks=True)
        self.assertEqual(c.post("/partner-admin/login/",{"username":"partner","password":"Orbit!Partner-2026"}).status_code,403)
        c.get("/partner-admin/login/")
        self.assertEqual(c.post("/partner-admin/login/",{"username":"partner","password":"Orbit!Partner-2026","csrfmiddlewaretoken":c.cookies["csrftoken"].value}).status_code,302)
        self.assertIn("no-store",c.get("/partner-admin/").headers["Cache-Control"])
        self.assertEqual(c.get("/partner-admin/logout/").status_code,405)
        self.assertEqual(c.post("/partner-admin/logout/").status_code,403)
        self.assertEqual(c.post("/partner-admin/logout/",{"csrfmiddlewaretoken":c.cookies["csrftoken"].value}).status_code,302)
        self.assertEqual(c.get("/partner-admin/").status_code,302)

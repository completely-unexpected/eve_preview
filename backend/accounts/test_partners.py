from django.test import TestCase, Client
from django.contrib.auth.hashers import check_password
from django.urls import reverse
from .models import User, PartnerAccount
from .admin import PartnerAccountForm


class PartnerTests(TestCase):
    def setUp(self):
        self.partner=PartnerAccount(username="partner",name="협력사")
        self.partner.set_password("Orbit!Partner-2026")
        self.partner.save()
        self.other=PartnerAccount(username="other",name="다른 협력사")
        self.other.set_password("Orbit!Other-2026")
        self.other.save()
        self.member=User.objects.create_user(username="child",nickname="내 회원",partner=self.partner)
        User.objects.create_user(username="private",nickname="다른 회원",partner=self.other)

    def signin(self):
        return self.client.post("/partner-admin/login/",{"username":"partner","password":"Orbit!Partner-2026"})

    def test_separate_credentials_and_sessions(self):
        self.assertEqual(self.signin().status_code,302)
        self.assertFalse(User.objects.filter(username="partner").exists())
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code,302)
        self.assertEqual(self.client.post("/api/accounts/login/",{"username":"partner","password":"Orbit!Partner-2026"}).status_code,400)
        self.assertEqual(self.client.get("/partner-admin/").status_code,200)

    def test_scope_minimal_fields_and_read_only(self):
        self.signin()
        data=self.client.get("/api/accounts/partner/members/?partner="+str(self.other.pk)).json()
        self.assertEqual(data["total"],1)
        self.assertEqual(data["items"][0]["nickname"],"내 회원")
        self.assertEqual(set(data["items"][0]),{"nickname","status","statusLabel","level","joinedAt"})
        self.assertEqual(self.client.post("/api/accounts/partner/members/").status_code,405)
        response=self.client.get("/partner-admin/")
        self.assertContains(response,"내 회원")
        self.assertNotContains(response,"다른 회원")

    def test_revoked_on_password_change_or_disable(self):
        self.signin()
        self.partner.set_password("New!Password-2026")
        self.partner.save()
        self.assertEqual(self.client.get("/partner-admin/").status_code,302)
        self.partner.set_password("Orbit!Partner-2026")
        self.partner.save()
        self.signin()
        self.partner.is_active=False
        self.partner.save()
        self.partner.is_active=True
        self.partner.save()
        self.assertEqual(self.client.get("/partner-admin/").status_code,302)

    def test_signup_attributes_only_to_partner(self):
        c=Client(enforce_csrf_checks=True)
        token=c.get("/api/accounts/session/").json()["csrfToken"]
        data={"username":"new","nickname":"신규", "password1":"Strong!Member-2026", "password2":"Strong!Member-2026", "referral_code":self.partner.referral_code.upper(), "is_partner":"true", "partner":self.other.pk}
        self.assertEqual(c.post("/api/accounts/signup/",data,HTTP_X_CSRFTOKEN=token).status_code,201)
        self.assertEqual(User.objects.get(username="new").partner,self.partner)
        self.assertEqual(PartnerAccount.objects.count(),2)
        data["username"]="bad"
        self.partner.is_active=False
        self.partner.save()
        self.assertEqual(c.post("/api/accounts/signup/",data,HTTP_X_CSRFTOKEN=token).status_code,400)

    def test_admin_creates_separate_account_and_hashes_password(self):
        form=PartnerAccountForm(data={"username":"issued","name":"관리자발급","is_active":True,"new_password":"Issued!Partner-2026","confirm_password":"Issued!Partner-2026"})
        self.assertTrue(form.is_valid(),form.errors)
        account=form.save()
        self.assertTrue(check_password("Issued!Partner-2026",account.password))
        self.assertNotEqual(account.password,"Issued!Partner-2026")
        self.assertEqual(len(account.referral_code),32)
        self.assertFalse(User.objects.filter(username="issued").exists())
        self.assertFalse(PartnerAccountForm(data={"username":"empty","name":"비번없음"}).is_valid())
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("admin:accounts_partneraccount_add")).status_code,302)

    def test_code_stable_and_pagination(self):
        code=self.partner.referral_code
        self.partner.save()
        self.assertEqual(code,self.partner.referral_code)
        User.objects.bulk_create([User(username="extra"+str(i),nickname="연결"+str(i),partner=self.partner) for i in range(21)])
        self.signin()
        data=self.client.get("/api/accounts/partner/members/").json()
        self.assertEqual(len(data["items"]),20)
        self.assertEqual(data["pages"],2)

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User, PartnerAccount


class ProfileForm(forms.Form):
    nickname = forms.CharField(label="닉네임", max_length=30)


class SignupForm(UserCreationForm):
    referral_code = forms.CharField(label="추천 코드", max_length=32, required=False)

    def clean_referral_code(self):
        code = self.cleaned_data.get("referral_code", "").strip().lower()
        if code and not PartnerAccount.objects.filter(referral_code=code, is_active=True).exists():
            raise forms.ValidationError("사용할 수 없는 추천 코드입니다.")
        return code

    nickname = forms.CharField(label="닉네임", max_length=30)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "nickname")
from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignupForm(UserCreationForm):
    nickname = forms.CharField(label="닉네임", max_length=30)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "nickname")
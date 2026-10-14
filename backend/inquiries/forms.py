from django import forms
class InquiryForm(forms.Form):
    title = forms.CharField(label="제목", max_length=200)
    body = forms.CharField(label="문의 내용", max_length=10000, widget=forms.Textarea)

from django import forms

class SMSForm(forms.Form):
    sms = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Paste SMS here'}),
        label="Transaction SMS"
    )

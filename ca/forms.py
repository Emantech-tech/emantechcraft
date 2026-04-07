from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.core.validators import MinLengthValidator

class SignUpForm(forms.ModelForm):
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}),
        validators=[MinLengthValidator(8)],
        label='Password'
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}),
        label='Confirm Password'
    )
    # OTP verification fields (handled in template, not in form)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Enter username'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email required
        self.fields['email'].required = True

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please login or use another email.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match. Please re-enter.")

        # Additional password validation
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")

        if password1 and password1.isdigit():
            raise forms.ValidationError("Password cannot be entirely numeric.")

        return password2

    def clean(self):
        cleaned_data = super().clean()
        # OTP verification is handled in the view, not in form
        return cleaned_data


class LoginForm(AuthenticationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Enter username or email',
            'class': 'form-control'
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Enter password',
            'class': 'form-control'
        })

    def confirm_login_allowed(self, user):
        """Override to add custom login restrictions if needed"""
        super().confirm_login_allowed(user)
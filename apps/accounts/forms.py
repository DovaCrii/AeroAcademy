from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import CharacterClass, Person

PASSWORD_MAX = 128


class TeamSignupForm(forms.Form):
    """Inscripción con el enlace del equipo: correo, nombre, contraseña (validadores de Django) y carrera opcional."""

    email = forms.EmailField(
        label="Correo", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    display_name = forms.CharField(label="Tu nombre", max_length=150, strip=True)
    password1 = forms.CharField(
        label="Contraseña",
        max_length=PASSWORD_MAX,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        max_length=PASSWORD_MAX,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    character_class = forms.ChoiceField(
        label="Carrera (opcional)",
        required=False,
        choices=[("", "La elijo después"), *CharacterClass.choices],
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        data = super().clean()
        one, two = data.get("password1"), data.get("password2")
        if one and two and one != two:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif one:
            candidate = Person(
                login=data.get("email", ""), display_name=data.get("display_name", "")
            )
            try:
                validate_password(one, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data


class SignupForm(forms.Form):
    """Registro con el enlace del admin: nombre, contraseña (con los validadores de Django) y carrera opcional."""

    display_name = forms.CharField(label="Tu nombre", max_length=150, strip=True)
    password1 = forms.CharField(
        label="Contraseña",
        max_length=PASSWORD_MAX,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        max_length=PASSWORD_MAX,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    character_class = forms.ChoiceField(
        label="Carrera (opcional)",
        required=False,
        choices=[("", "La elijo después"), *CharacterClass.choices],
    )

    def __init__(self, *args, person, **kwargs):
        super().__init__(*args, **kwargs)
        self.person = person

    def clean(self):
        data = super().clean()
        one, two = data.get("password1"), data.get("password2")
        if one and two and one != two:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif one:
            self.person.display_name = data.get("display_name") or self.person.display_name
            try:
                validate_password(one, user=self.person)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data


class AccountPasswordChangeForm(PasswordChangeForm):
    """Cambio de contraseña de quien ya tiene sesión con contraseña: pide la actual y valida la nueva."""

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Contraseña nueva"
        self.fields["new_password2"].label = "Repite la contraseña nueva"
        for name in self.fields:
            self.fields[name].max_length = PASSWORD_MAX

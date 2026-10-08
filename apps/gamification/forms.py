from urllib.parse import urlparse

from django import forms

from apps.accounts.models import CharacterClass

from . import game
from .models import Title

LINK_HOSTS = {"linkedin": ("linkedin.com",), "credly": ("credly.com",)}


class SheetForm(forms.Form):
    headline = forms.CharField(label="Titular profesional", max_length=90, required=False)
    bio = forms.CharField(
        label="Sobre mí", max_length=600, required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    character_class = forms.ChoiceField(
        label="Clase", choices=[("", "Sin clase")] + list(CharacterClass.choices), required=False
    )
    selected_title = forms.ModelChoiceField(
        label="Título que muestro",
        queryset=Title.objects.none(),
        required=False,
        empty_label="El más alto",
    )
    linkedin = forms.URLField(label="LinkedIn", required=False, assume_scheme="https")
    credly = forms.URLField(label="Credly", required=False, assume_scheme="https")
    show_game_view = forms.BooleanField(label="Mostrar mi hoja en vista de juego", required=False)

    def __init__(self, *args, person, **kwargs):
        super().__init__(*args, **kwargs)
        self.person = person
        # Solo se puede elegir entre los títulos ya desbloqueados (validación en el servidor).
        ids = [t.pk for t in game.available_titles(person)]
        self.fields["selected_title"].queryset = Title.objects.filter(pk__in=ids)

    @classmethod
    def initial_for(cls, person):
        return {
            "headline": person.headline,
            "bio": person.bio,
            "character_class": person.character_class,
            "selected_title": person.selected_title_id,
            "linkedin": person.links.get("linkedin", ""),
            "credly": person.links.get("credly", ""),
            "show_game_view": person.show_game_view,
        }

    def _clean_link(self, name):
        value = self.cleaned_data.get(name, "")
        if not value:
            return ""
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        ok = any(host == h or host.endswith("." + h) for h in LINK_HOSTS[name])
        if parsed.scheme != "https" or not ok:
            raise forms.ValidationError(f"Debe ser un enlace https de {LINK_HOSTS[name][0]}.")
        return value

    def clean_linkedin(self):
        return self._clean_link("linkedin")

    def clean_credly(self):
        return self._clean_link("credly")

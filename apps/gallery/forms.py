"""Form della galleria: caricamento (anche multiplo) e modifica."""
from django import forms

from apps.core.forms import BaseBootstrapModelForm

from .models import GalleryPhoto, GalleryTag


class _MultipleFileInput(forms.FileInput):
    """Widget che accetta più file in una sola scelta."""

    allow_multiple_selected = True


class _MultipleFileField(forms.FileField):
    """Campo file che accetta e restituisce una lista di file (multi-upload)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", _MultipleFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        singolo = super().clean
        if isinstance(data, (list, tuple)):
            return [singolo(voce, initial) for voce in data]
        return [singolo(data, initial)]


class _TagsMixin(forms.Form):
    """Etichette esistenti + nuove etichette scritte al volo."""

    tags = forms.ModelMultipleChoiceField(
        label="Etichette",
        queryset=GalleryTag.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text="Tieni premuto Ctrl per selezionare più etichette.",
    )
    new_tags = forms.CharField(
        label="Nuove etichette",
        required=False,
        help_text="Separate da virgola: vengono create e assegnate (es. piscina grigia, scala ad angolo).",
    )


class GalleryUploadForm(_TagsMixin, BaseBootstrapModelForm):
    """Caricamento di una o più foto con le stesse etichette."""

    images = _MultipleFileField(
        label="Foto",
        help_text="Puoi scegliere più foto insieme.",
    )

    class Meta:
        model = GalleryPhoto
        fields = ["title", "description", "job", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.jobs.models import Job

        self.fields["job"].queryset = (
            Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name")
        )
        self.fields["job"].required = False


class GalleryPhotoForm(_TagsMixin, BaseBootstrapModelForm):
    class Meta:
        model = GalleryPhoto
        fields = ["title", "description", "image", "job", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.jobs.models import Job

        self.fields["image"].required = False
        self.fields["image"].help_text = "Lascia vuoto per tenere la foto attuale."
        self.fields["job"].queryset = (
            Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name")
        )
        self.fields["job"].required = False

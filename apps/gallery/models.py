"""Galleria fotografica con etichette (es. piscine per colore, forma, accessori)."""
from django.conf import settings
from django.db import models

from apps.core.models import Tag, TimeStampedModel
from apps.core.validators import valida_file_caricato


class GalleryTag(models.Model):
    """Etichetta della galleria (es. «piscina grigia», «scala ad angolo»)."""

    name = models.CharField("Nome", max_length=60, unique=True)
    color = models.CharField("Colore", max_length=20, choices=Tag.COLOR_CHOICES, default="secondary")

    class Meta:
        verbose_name = "Etichetta galleria"
        verbose_name_plural = "Etichette galleria"
        ordering = ["name"]

    def __str__(self):
        return self.name


class GalleryPhoto(TimeStampedModel):
    """Foto della galleria, con più etichette per la ricerca."""

    title = models.CharField("Titolo", max_length=150, blank=True)
    description = models.TextField("Descrizione", blank=True)
    image = models.ImageField("Foto", upload_to="gallery/%Y/%m/", validators=[valida_file_caricato])
    tags = models.ManyToManyField(GalleryTag, blank=True, related_name="photos", verbose_name="Etichette")
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gallery_photos",
        verbose_name="Cantiere",
    )
    active = models.BooleanField("Visibile in galleria", default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gallery_photos",
        verbose_name="Caricata da",
    )

    class Meta:
        verbose_name = "Foto galleria"
        verbose_name_plural = "Galleria"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.title or self.image.name.rsplit("/", 1)[-1]

    def save(self, *args, **kwargs):
        # come per gli allegati: le foto nuove vengono raddrizzate e compresse
        if self.image and not getattr(self.image, "_committed", True):
            from apps.core.images import comprimi_immagine

            comprimi_immagine(self.image)
        return super().save(*args, **kwargs)

    @property
    def size_kb(self):
        try:
            return round(self.image.size / 1024, 1)
        except Exception:
            return None

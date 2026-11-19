from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    phone = models.CharField("Telefono", max_length=40, blank=True)
    password_email = models.TextField(
        "Password della casella email (cifrata)",
        blank=True,
        editable=False,
        help_text="Serve a spedire dal gestionale con la propria casella (es. simone@aquaforma.it).",
    )

    class Meta:
        verbose_name = "Utente"
        verbose_name_plural = "Utenti"

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        first = (self.first_name or self.username or "?")[0]
        last = (self.last_name or "")[:1]
        return f"{first}{last}".upper()

    # ------------------------------------------------- casella personale
    @property
    def password_casella(self):
        """Password della casella personale, in chiaro (vuota se non salvata)."""
        from apps.core.cifratura import decifra

        return decifra(self.password_email)

    def imposta_password_casella(self, password):
        from apps.core.cifratura import cifra

        self.password_email = cifra(password or "")

    @property
    def ha_casella_personale(self):
        """True se le email di questo utente partono dalla sua casella."""
        return bool((self.email or "").strip() and self.password_casella)

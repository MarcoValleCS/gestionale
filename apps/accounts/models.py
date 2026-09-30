from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    phone = models.CharField("Telefono", max_length=40, blank=True)

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

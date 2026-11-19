"""Test dei messaggi interni fra utenti."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import InternalMessage

Utente = get_user_model()


class MessaggiInterniTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.marco = Utente.objects.create_user("marco", "marco@example.com", "password123!", first_name="Marco", last_name="Rossi")
        cls.sara = Utente.objects.create_user("sara", "sara@example.com", "password123!", first_name="Sara", last_name="Bianchi")
        cls.estraneo = Utente.objects.create_user("estraneo", "estraneo@example.com", "password123!")

    def login(self, utente=None):
        self.client.force_login(utente or self.marco)

    def test_invio_di_un_messaggio(self):
        self.login()
        risposta = self.client.post(reverse("core:messaggi"), {"recipient": self.sara.pk, "body": "Ciao Sara!"})
        self.assertEqual(risposta.status_code, 302)
        messaggio = InternalMessage.objects.get()
        self.assertEqual(messaggio.sender, self.marco)
        self.assertEqual(messaggio.recipient, self.sara)
        self.assertFalse(messaggio.is_read)

    def test_la_conversazione_mostra_i_messaggi(self):
        InternalMessage.objects.create(sender=self.marco, recipient=self.sara, body="Ciao Sara")
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Ciao Marco")
        self.login()
        risposta = self.client.get(reverse("core:conversazione", args=[self.sara.pk]))
        self.assertContains(risposta, "Ciao Sara")
        self.assertContains(risposta, "Ciao Marco")

    def test_apertura_segna_come_letto(self):
        messaggio = InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Leggimi")
        self.login()
        self.client.get(reverse("core:conversazione", args=[self.sara.pk]))
        messaggio.refresh_from_db()
        self.assertTrue(messaggio.is_read)

    def test_il_pallino_dei_messaggi_non_letti(self):
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Uno")
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Due")
        self.login()
        risposta = self.client.get(reverse("core:home"))
        self.assertContains(risposta, "badge text-bg-danger ms-auto")
        self.assertEqual(risposta.context["messaggi_non_letti"], 2) if risposta.context else None

    def test_ognuno_vede_solo_le_sue_conversazioni(self):
        InternalMessage.objects.create(sender=self.marco, recipient=self.sara, body="Segreto tra noi")
        self.login(self.estraneo)
        risposta = self.client.get(reverse("core:messaggi"))
        self.assertNotContains(risposta, "Segreto tra noi")

    def test_non_si_puo_scrivere_a_se_stessi(self):
        self.login()
        risposta = self.client.post(reverse("core:messaggi"), {"recipient": self.marco.pk, "body": "Ciao me"})
        self.assertEqual(risposta.status_code, 200)
        self.assertFalse(InternalMessage.objects.exists())

    def test_risposta_dal_modulo_della_conversazione(self):
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Domanda")
        self.login()
        self.client.post(reverse("core:conversazione", args=[self.sara.pk]), {"body": "Risposta"})
        self.assertEqual(InternalMessage.objects.filter(sender=self.marco, recipient=self.sara, body="Risposta").count(), 1)

    def test_elenco_conversazioni_con_non_letti(self):
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Uno")
        InternalMessage.objects.create(sender=self.marco, recipient=self.sara, body="Due")
        self.login()
        risposta = self.client.get(reverse("core:messaggi"))
        self.assertEqual(risposta.context["non_letti"], 1)
        self.assertEqual(len(risposta.context["conversazioni"]), 1)


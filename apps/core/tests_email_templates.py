"""Test dei modelli email personalizzabili."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .email_templates import contenuto
from .models import EmailTemplate

User = get_user_model()


class EmailTemplateTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")

    def setUp(self):
        self.client.force_login(self.user)

    def test_usa_il_predefinito_finche_non_personalizzato(self):
        oggetto, corpo = contenuto(EmailTemplate.KIND_INVOICE, {"numero": "F-1", "azienda": "Aquaforma"})
        self.assertEqual(oggetto, "Fattura F-1 – Aquaforma")
        self.assertIn("F-1", corpo)

    def test_usa_il_modello_personalizzato(self):
        EmailTemplate.objects.create(kind=EmailTemplate.KIND_INVOICE, subject="Ciao {cliente}", body="Testo {numero}")
        oggetto, corpo = contenuto(EmailTemplate.KIND_INVOICE, {"cliente": "Rossi", "numero": "F-1"})
        self.assertEqual(oggetto, "Ciao Rossi")
        self.assertEqual(corpo, "Testo F-1")

    def test_pagina_modelli_salva(self):
        risposta = self.client.get(reverse("core:email_templates"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Modelli email")

        risposta = self.client.post(
            reverse("core:email_templates"),
            {
                "subject_quote": "Preventivo {numero}",
                "body_quote": "Buongiorno {cliente}",
                "subject_invoice": "Fattura {numero}",
                "body_invoice": "Buongiorno {cliente}",
                "subject_quote_reminder": "Sollecito {numero}",
                "body_quote_reminder": "Buongiorno {cliente}",
                "subject_invoice_reminder": "Sollecito {numero}",
                "body_invoice_reminder": "Buongiorno {cliente}",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        self.assertTrue(EmailTemplate.objects.filter(kind="quote", subject="Preventivo {numero}").exists())
        self.assertTrue(EmailTemplate.objects.filter(kind="invoice_reminder").exists())

    def test_oggetto_obbligatorio(self):
        self.client.post(
            reverse("core:email_templates"),
            {
                "subject_quote": "",
                "body_quote": "x",
                "subject_invoice": "F",
                "body_invoice": "x",
                "subject_quote_reminder": "S",
                "body_quote_reminder": "x",
                "subject_invoice_reminder": "S",
                "body_invoice_reminder": "x",
            },
        )
        self.assertFalse(EmailTemplate.objects.exists())

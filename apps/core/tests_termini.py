"""Test delle condizioni di vendita standard e della pagina pubblica /termini."""
from django.test import TestCase
from django.urls import reverse

from apps.core.email_templates import contenuto
from apps.core.models import CompanySettings, EmailTemplate


class TerminiVenditaTest(TestCase):
    def test_pagina_pubblica_senza_login(self):
        risposta = self.client.get(reverse("core:termini"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Condizioni generali di vendita")
        self.assertContains(risposta, "recesso")
        self.assertContains(risposta, "Garanzie")

    def test_pagina_usa_i_dati_azienda(self):
        company = CompanySettings.load()
        company.name = "Aquaforma srl"
        company.vat_number = "01234567890"
        company.save()
        risposta = self.client.get(reverse("core:termini"))
        self.assertContains(risposta, "Aquaforma srl")
        self.assertContains(risposta, "01234567890")

    def test_testo_personalizzato_con_segnaposto(self):
        company = CompanySettings.load()
        company.name = "Prova SpA"
        company.sales_terms = "<p>Termini di {azienda}, P.IVA {piva}.</p>"
        company.vat_number = "00000000000"
        company.save()
        risposta = self.client.get(reverse("core:termini"))
        self.assertContains(risposta, "Termini di Prova SpA, P.IVA 00000000000.")

    def test_nuovo_preventivo_include_la_riga_termini(self):
        from django.contrib.auth import get_user_model

        admin = get_user_model().objects.create_superuser("admin", "a@example.com", "password123!")
        self.client.force_login(admin)
        risposta = self.client.get(reverse("sales:quote_create"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Condizioni di vendita disponibili su:")
        self.assertContains(risposta, "aquaforma.space/termini")
        self.assertNotContains(risposta, "caparra confirmatoria")

    def test_note_conservano_link_sicuri(self):
        from apps.core.richtext import clean_notes

        pulito = clean_notes(
            'Vedi <a href="https://aquaforma.space/termini">termini</a> '
            'e <a href="javascript:alert(1)">no</a>.'
        )
        self.assertIn('href="https://aquaforma.space/termini"', pulito)
        self.assertNotIn("javascript:", pulito)

    def test_linkify_urls_solo_testo_in_chiaro(self):
        from apps.core.templatetags.core_extras import linkify_urls

        fuori = linkify_urls("Condizioni su: aquaforma.space/termini.")
        self.assertIn('<a href="https://aquaforma.space/termini">aquaforma.space/termini</a>.', fuori)
        gia = linkify_urls('<a href="https://a.it/x">a.it/x</a> e b.it/y.')
        self.assertEqual(gia.count("<a "), 2)
        self.assertIn('<a href="https://b.it/y">b.it/y</a>.', gia)
        # niente falsi positivi: file e abbreviazioni restano testo
        self.assertNotIn("<a ", linkify_urls("vedi allegato fattura.pdf e art. 1490 c.c."))

    def test_email_preventivo_con_link_termini(self):
        _oggetto, corpo = contenuto(
            EmailTemplate.KIND_QUOTE,
            {
                "cliente": "Rossi",
                "numero": "PRE-1",
                "data": "08/10/2026",
                "totale": "100,00",
                "azienda": "Aquaforma",
                "validita": "",
                "termini": "Condizioni generali di vendita: https://aquaforma.space/termini\n",
            },
        )
        self.assertIn("https://aquaforma.space/termini", corpo)

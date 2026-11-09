"""Test delle protezioni aggiunte con la verifica di sicurezza (novembre 2026).

- Le azioni che cambiano lo stato dei documenti non partono con un semplice
  link o un'immagine (GET): solo da modulo, con il token CSRF.
- L'HTML delle email in arrivo non può far partire richieste verso il
  gestionale né coprire la pagina con un finto avviso.
- Un collaboratore esterno scarica solo i propri file.
- Margini e statistiche restano a vendite e amministrazione.
- Le password scelte dall'amministratore seguono le regole di sicurezza e un
  amministratore «di ruolo» non può prendere il posto di un superutente.
"""
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.forms import UserCreateForm, UserUpdateForm
from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import Attachment, UnitOfMeasure, VatRate
from apps.core.richtext import clean_email_html
from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import register_movement
from apps.sales.models import Quote, SalesOrder

User = get_user_model()


class AzioniSoloPostTest(TestCase):
    """Un GET (link, immagine in un'email) non deve cambiare nulla."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.cliente = Contact.objects.create(name="Cliente GET", is_customer=True)
        cls.articolo = Product.objects.create(
            name="Rubinetto", uom=cls.uom, sale_price=Decimal("10"), sale_vat=cls.vat,
            purchase_price=Decimal("5"), purchase_vat=cls.vat,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _preventivo(self):
        preventivo = Quote.objects.create(customer=self.cliente)
        preventivo.lines.create(
            product=self.articolo, description="x", qty=Decimal("1"), uom=self.uom,
            unit_price=Decimal("10"), vat_rate=self.vat,
        )
        return preventivo

    def test_conversione_preventivo_con_get_non_crea_ordini(self):
        preventivo = self._preventivo()
        risposta = self.client.get(reverse("sales:quote_convert", args=[preventivo.pk]))
        self.assertRedirects(risposta, reverse("sales:quote_detail", args=[preventivo.pk]))
        self.assertFalse(SalesOrder.objects.filter(source_quote=preventivo).exists())
        preventivo.refresh_from_db()
        self.assertNotEqual(preventivo.status, Quote.STATUS_CONVERTED)

    def test_cambi_di_stato_del_preventivo_con_get_non_fanno_nulla(self):
        preventivo = self._preventivo()
        for nome in ("sales:quote_send", "sales:quote_accept", "sales:quote_reject", "sales:quote_duplicate"):
            with self.subTest(nome=nome):
                self.client.get(reverse(nome, args=[preventivo.pk]))
                preventivo.refresh_from_db()
                self.assertEqual(preventivo.status, Quote.STATUS_DRAFT)
        self.assertEqual(Quote.objects.count(), 1, "il GET non deve duplicare il preventivo")

    def test_consegna_ordine_con_get_non_scarica_il_magazzino(self):
        register_movement(
            product=self.articolo, delta=Decimal("10"), movement_type=StockMovement.TYPE_LOAD,
            warehouse=Warehouse.get_default(),
        )
        ordine = SalesOrder.objects.create(customer=self.cliente, status=SalesOrder.STATUS_CONFIRMED)
        ordine.lines.create(
            product=self.articolo, description="x", qty=Decimal("2"), uom=self.uom,
            unit_price=Decimal("10"), vat_rate=self.vat,
        )
        movimenti = StockMovement.objects.count()
        for nome in ("sales:order_deliver", "sales:order_confirm"):
            with self.subTest(nome=nome):
                self.client.get(reverse(nome, args=[ordine.pk]))
        self.assertEqual(StockMovement.objects.count(), movimenti)
        ordine.refresh_from_db()
        self.assertEqual(ordine.status, SalesOrder.STATUS_CONFIRMED)

    def test_disattivazione_contatto_con_get_non_fa_nulla(self):
        self.client.get(reverse("contacts:toggle_active", args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.active)

    def test_con_post_le_azioni_funzionano_ancora(self):
        preventivo = self._preventivo()
        self.client.post(reverse("sales:quote_convert", args=[preventivo.pk]))
        self.assertTrue(SalesOrder.objects.filter(source_quote=preventivo).exists())


class EmailHtmlTest(TestCase):
    """L'HTML di un'email ricevuta resta dentro il suo riquadro."""

    def test_le_immagini_con_indirizzo_del_gestionale_vengono_tolte(self):
        html = '<p>Ciao</p><img src="/vendite/ordini/5/consegna/"><img src="//altro.example/x.png">'
        pulito = clean_email_html(html)
        self.assertIn("Ciao", pulito)
        self.assertNotIn("/vendite/", pulito)
        self.assertNotIn("altro.example", pulito)

    def test_i_link_relativi_vengono_tolti_quelli_completi_restano(self):
        pulito = clean_email_html('<a href="/accounts/logout/">esci</a><a href="https://aquaforma.it">sito</a>')
        self.assertNotIn("/accounts/logout/", pulito)
        self.assertIn('href="https://aquaforma.it"', pulito)

    def test_le_classi_della_pagina_non_si_possono_usare(self):
        pulito = clean_email_html('<div class="position-fixed top-0 start-0 w-100 h-100">Sessione scaduta</div>')
        self.assertIn("Sessione scaduta", pulito)
        self.assertNotIn("position-fixed", pulito)

    def test_gli_stili_che_caricano_indirizzi_vengono_tolti(self):
        for stile in ("background: url(/vendite/x)", "list-style: url(/x)", "background-image: u\\72l(/x)"):
            with self.subTest(stile=stile):
                pulito = clean_email_html(f'<p style="{stile}">testo</p>')
                self.assertNotIn("url", pulito)
                self.assertNotIn("/x", pulito)

    def test_gli_stili_normali_restano(self):
        pulito = clean_email_html('<p style="color: red; background-color: #fff">testo</p>')
        self.assertIn("color", pulito)
        self.assertIn("background-color", pulito)


class MediaCollaboratoreTest(TestCase):
    """Il collaboratore scarica solo le proprie foto e il logo."""

    @classmethod
    def setUpClass(cls):
        # Prima di super(): setUpTestData salva i file e devono finire nella
        # cartella temporanea, non nei media veri.
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        from apps.hr.models import Collaborator
        from apps.jobs.models import Job

        cls.utente = User.objects.create_user("scavi", password="password123!")
        cls.utente.groups.add(Group.objects.get(name="Collaboratore"))
        cls.collaboratore = Collaborator.objects.create(name="Scavi Rossi", user=cls.utente)
        cls.altro = Collaborator.objects.create(name="Altro")
        cliente = Contact.objects.create(name="Cliente Media", is_customer=True)
        cantiere = Job.objects.create(name="Cantiere Media", customer=cliente)

        def allegato(nome, **destinazione):
            return Attachment.objects.create(
                name=nome, file=SimpleUploadedFile(nome, b"contenuto", content_type="image/png"), **destinazione
            )

        cls.mia = allegato("mia.png", collaborator=cls.collaboratore, job=cantiere)
        cls.sua = allegato("sua.png", collaborator=cls.altro, job=cantiere)
        cls.contratto = allegato("contratto.pdf", job=cantiere)

    def url(self, allegato):
        return "/media/" + allegato.file.name

    def test_vede_la_propria_foto(self):
        self.client.force_login(self.utente)
        self.assertEqual(self.client.get(self.url(self.mia)).status_code, 200)

    def test_non_vede_i_file_degli_altri(self):
        self.client.force_login(self.utente)
        for allegato in (self.sua, self.contratto):
            with self.subTest(file=allegato.file.name):
                self.assertEqual(self.client.get(self.url(allegato)).status_code, 404)

    def test_il_percorso_del_logo_non_apre_altri_file(self):
        self.client.force_login(self.utente)
        risposta = self.client.get("/media/company/../" + self.contratto.file.name)
        self.assertEqual(risposta.status_code, 404)

    def test_l_ufficio_vede_tutto(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.url(self.contratto)).status_code, 200)


class StatisticheRiservateTest(TestCase):
    def test_il_magazzino_non_vede_le_statistiche(self):
        magazzino = User.objects.create_user("magazzino", password="password123!")
        magazzino.groups.add(Group.objects.get(name="Magazzino"))
        self.client.force_login(magazzino)
        self.assertEqual(self.client.get(reverse("sales:statistics")).status_code, 403)
        dashboard = self.client.get(reverse("core:home"))
        self.assertNotContains(dashboard, "Statistiche complete")

    def test_le_vendite_vedono_le_statistiche(self):
        vendite = User.objects.create_user("vendite", password="password123!")
        vendite.groups.add(Group.objects.get(name="Vendite"))
        self.client.force_login(vendite)
        self.assertEqual(self.client.get(reverse("sales:statistics")).status_code, 200)


class UtentiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ruolo_vendite = Group.objects.get(name="Vendite")

    def _dati(self, password):
        return {
            "username": "nuovo", "first_name": "Nuovo", "last_name": "Utente", "email": "nuovo@example.com",
            "phone": "", "groups": [self.ruolo_vendite.pk], "is_active": True,
            "password1": password, "password2": password,
        }

    def test_password_comune_rifiutata_alla_creazione(self):
        form = UserCreateForm(data=self._dati("1234567890"))
        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)

    def test_password_robusta_accettata(self):
        form = UserCreateForm(data=self._dati("Lampada-Verde-Fiume-42"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_password_comune_rifiutata_alla_modifica(self):
        utente = User.objects.create_user("esistente", password="Lampada-Verde-Fiume-42")
        dati = self._dati("")
        dati.update(username="esistente", new_password="password123")
        form = UserUpdateForm(data=dati, instance=utente)
        self.assertFalse(form.is_valid())
        self.assertIn("new_password", form.errors)

    def test_amministratore_di_ruolo_non_modifica_un_superutente(self):
        capo = User.objects.create_superuser("capo", "capo@example.com", "password123!")
        amministratore = User.objects.create_user("ufficio", password="password123!")
        amministratore.groups.add(Group.objects.get(name="Amministratore"))
        self.client.force_login(amministratore)
        self.assertEqual(self.client.get(reverse("accounts:user_update", args=[capo.pk])).status_code, 404)
        elenco = self.client.get(reverse("accounts:user_list"))
        self.assertNotContains(elenco, reverse("accounts:user_update", args=[capo.pk]))


class TokenNonAsciiTest(TestCase):
    @override_settings(LEAD_SITO_TOKEN="token-di-prova-per-i-test")
    def test_token_lead_non_ascii_risponde_403(self):
        risposta = self.client.post(
            reverse("leads:lead_da_sito"), data="{}", content_type="application/json",
            HTTP_X_LEAD_TOKEN="tökén-sbagliato",
        )
        self.assertEqual(risposta.status_code, 403)

    def test_token_mcp_non_ascii_non_valido(self):
        import os
        import sys
        from pathlib import Path
        from unittest import mock

        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        try:
            from mcp_auth import verifica_token
        finally:
            sys.path.pop(0)
        with mock.patch.dict(os.environ, {"MCP_TOKENS": "giusto:admin", "MCP_TOKEN": ""}):
            self.assertIsNone(verifica_token("tökén"))
            self.assertIsNotNone(verifica_token("giusto"))


class PdfSenzaRisorseEsterneTest(TestCase):
    def test_il_pdf_non_apre_file_locali_ne_indirizzi(self):
        from unittest import mock

        from apps.core import pdf

        if not pdf.pdf_available():
            self.skipTest("WeasyPrint non disponibile")
        import weasyprint

        richieste = []
        originale = weasyprint.URLFetcher.fetch

        def registra(fetcher, url, *args, **kwargs):
            richieste.append((url, getattr(fetcher, "_allowed_protocols", None)))
            return originale(fetcher, url, *args, **kwargs)

        with mock.patch.object(weasyprint.URLFetcher, "fetch", registra), self.assertLogs("weasyprint", "ERROR"):
            documento = pdf.render_pdf('<p>x</p><img src="file:///etc/passwd"><img src="http://127.0.0.1:9/a.png">')
        self.assertTrue(documento.startswith(b"%PDF"))
        self.assertEqual(len(richieste), 2)
        for url, protocolli in richieste:
            with self.subTest(url=url):
                self.assertEqual(set(protocolli or ()), {"data"}, "solo i data-URI possono essere caricati")

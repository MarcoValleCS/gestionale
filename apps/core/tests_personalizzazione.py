"""Test della personalizzazione grafica: colori, logo, compressione immagini."""
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Product
from apps.core.models import UnitOfMeasure, VatRate
from apps.hr.models import Collaborator

from .images import comprimi_immagine
from .models import Attachment, CompanySettings
from .utils import mescola_colori, normalizza_colore, rgba, schiarisci, scurisci

User = get_user_model()


def immagine_png(larghezza=2000, altezza=1500, colore=(20, 90, 200)):
    """Un PNG pieno, come quelli che escono dal telefono (ma più leggero)."""
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (larghezza, altezza), colore).save(buffer, format="PNG")
    return buffer.getvalue()


class ColoriTest(TestCase):
    def test_colore_valido_normalizzato(self):
        self.assertEqual(normalizza_colore("#AABBCC"), "#aabbcc")
        self.assertEqual(normalizza_colore("  #123456  "), "#123456")

    def test_colore_non_valido_usa_il_fallback(self):
        for valore in ("", None, "rosso", "#12345", "#zzzzzz", "123456"):
            with self.subTest(valore=valore):
                self.assertEqual(normalizza_colore(valore), "#2563eb")
                self.assertEqual(normalizza_colore(valore, "#000000"), "#000000")

    def test_mescola_colori(self):
        self.assertEqual(mescola_colori("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(mescola_colori("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(mescola_colori("#000000", "#ffffff", 0.5), "#808080")

    def test_scurisci_e_schiarisci(self):
        self.assertEqual(scurisci("#ffffff", 1), "#000000")
        self.assertEqual(schiarisci("#000000", 1), "#ffffff")
        # scurire un colore non lo lascia identico
        self.assertNotEqual(scurisci("#2563eb"), "#2563eb")

    def test_rgba(self):
        self.assertEqual(rgba("#2563eb", 0.5), "rgba(37, 99, 235, 0.5)")


class CompanySettingsAspettoTest(TestCase):
    def test_valori_predefiniti(self):
        azienda = CompanySettings.load()
        self.assertEqual(azienda.theme_color_hex, "#2563eb")
        self.assertEqual(azienda.background_hex, "#f4f6fb")
        self.assertEqual(azienda.document_style, "classico")
        self.assertEqual(azienda.theme_background, "soft")

    def test_colori_derivati_dal_colore_principale(self):
        azienda = CompanySettings.load()
        azienda.theme_color = "#c81e1e"
        azienda.save()
        self.assertEqual(azienda.theme_color_hex, "#c81e1e")
        self.assertNotEqual(azienda.theme_color_dark, azienda.theme_color_hex)
        self.assertNotEqual(azienda.theme_color_soft, azienda.theme_color_hex)
        laterale = azienda.sidebar_colors
        for chiave in ("top", "mid", "bottom", "glow", "active"):
            self.assertIn(chiave, laterale)

    def test_sfondo_per_preset(self):
        azienda = CompanySettings.load()
        for valore, atteso in CompanySettings.BACKGROUND_COLORS.items():
            with self.subTest(valore=valore):
                azienda.theme_background = valore
                self.assertEqual(azienda.background_hex, atteso)

    def test_colore_non_valido_non_rompe_il_tema(self):
        azienda = CompanySettings.load()
        azienda.theme_color = "non-un-colore"
        azienda.save()
        self.assertEqual(azienda.theme_color_hex, "#2563eb")

    def test_logo_del_gestionale_ricade_su_quello_aziendale(self):
        azienda = CompanySettings.load()
        self.assertEqual(azienda.app_logo_url, "")
        azienda.logo = "company/logo.png"
        self.assertEqual(azienda.app_logo_url, "/media/company/logo.png")
        azienda.app_logo = "company/app.png"
        self.assertEqual(azienda.app_logo_url, "/media/company/app.png")


class TemaNeiTemplateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("tema", "tema@example.com", "password123!")
        self.client.force_login(self.user)

    def test_il_colore_scelto_finisce_nella_pagina(self):
        azienda = CompanySettings.load()
        azienda.theme_color = "#ff8800"
        azienda.theme_background = "warm"
        azienda.save()

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("--brand: #ff8800", html)
        self.assertIn("--bg: #faf7f1", html)
        self.assertIn("--sidebar-top", html)

    def test_lo_stile_documenti_finisce_nella_stampa(self):
        from apps.sales.models import Quote

        azienda = CompanySettings.load()
        azienda.document_style = "sobrio"
        azienda.save()

        from apps.contacts.models import Contact

        cliente = Contact.objects.create(name="Cliente Stile", is_customer=True)
        preventivo = Quote.objects.create(customer=cliente)
        response = self.client.get(reverse("sales:quote_print", args=[preventivo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("stile-sobrio", response.content.decode())


class CompressioneImmaginiTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.product = Product.objects.create(name="Articolo foto", uom=cls.uom, sale_vat=cls.vat, purchase_vat=cls.vat)

    def test_foto_grande_compresa_e_raddrizzata_in_jpeg(self):
        caricato = SimpleUploadedFile("foto.png", immagine_png(2400, 1800), content_type="image/png")
        allegato = Attachment(name="Foto", product=self.product, file=caricato)
        allegato.save()

        from PIL import Image

        allegato.refresh_from_db()
        self.assertTrue(allegato.file.name.endswith(".jpg"), allegato.file.name)
        with Image.open(allegato.file.path) as immagine:
            self.assertLessEqual(max(immagine.size), 1600)
        self.assertLess(allegato.file.size, len(immagine_png(2400, 1800)))

    def test_immagine_piccola_resta_com_e(self):
        dati = immagine_png(120, 90)
        caricato = SimpleUploadedFile("piccola.png", dati, content_type="image/png")
        allegato = Attachment(name="Piccola", product=self.product, file=caricato)
        allegato.save()
        allegato.refresh_from_db()
        # sotto i 1600 px e già leggera: il PNG originale resta
        self.assertTrue(allegato.file.name.endswith(".png"))

    def test_file_non_immagine_non_viene_toccato(self):
        caricato = SimpleUploadedFile("bolla.pdf", b"%PDF-1.4 finto", content_type="application/pdf")
        allegato = Attachment(name="Bolla", product=self.product, file=caricato)
        allegato.save()
        allegato.refresh_from_db()
        self.assertTrue(allegato.file.name.endswith(".pdf"))
        self.assertEqual(allegato.file.size, len(b"%PDF-1.4 finto"))

    def test_funzione_diretta_su_file_non_immagine(self):
        from django.core.files.base import ContentFile

        campo = ContentFile(b"non sono un'immagine", name="testo.txt")
        self.assertIsNone(comprimi_immagine(campo))


class AllegatoConTipoTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.product = Product.objects.create(name="Articolo foto", uom=cls.uom, sale_vat=cls.vat, purchase_vat=cls.vat)
        cls.collaboratore = Collaborator.objects.create(name="Foto Tester")

    def test_allegato_di_un_collaboratore_senza_articolo(self):
        allegato = Attachment(
            name="Foto cantiere",
            file=SimpleUploadedFile("foto.txt", b"contenuto", content_type="text/plain"),
            collaborator=self.collaboratore,
            kind=Attachment.KIND_SITE,
        )
        allegato.save()
        self.assertEqual(allegato.kind, Attachment.KIND_SITE)
        self.assertIn(allegato, self.collaboratore.photos.all())

    def test_allegato_senza_destinazione_rifiutato(self):
        allegato = Attachment(
            name="Senza niente",
            file=SimpleUploadedFile("foto.txt", b"contenuto", content_type="text/plain"),
        )
        with self.assertRaises(IntegrityError):
            allegato.save()

    def test_tipi_disponibili(self):
        valori = {valore for valore, _ in Attachment.KIND_CHOICES}
        self.assertEqual(valori, {"document", "site", "receipt"})


class FormAziendaTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_superuser("azienda", "az@example.com", "password123!")
        self.client.force_login(self.user)

    def test_salvataggio_con_logo_e_tema(self):
        response = self.client.post(
            reverse("core:company_update"),
            {
                "name": "Aquaforma srl",
                "vat_number": "04852690165",
                "fiscal_regime": "RF01",
                "country": "Italia",
                "theme_color": "#0f766e",
                "theme_background": "grey",
                "document_style": "moderno",
                "document_color": "#0f766e",
                "logo": SimpleUploadedFile("logo.png", immagine_png(200, 80), content_type="image/png"),
                "app_logo": SimpleUploadedFile("app.png", immagine_png(120, 120), content_type="image/png"),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        azienda = CompanySettings.load()
        self.assertEqual(azienda.name, "Aquaforma srl")
        self.assertEqual(azienda.theme_color, "#0f766e")
        self.assertEqual(azienda.theme_background, "grey")
        self.assertEqual(azienda.document_style, "moderno")
        self.assertTrue(azienda.logo)
        self.assertTrue(azienda.app_logo)
        self.assertTrue(azienda.app_logo_url.endswith(".jpg") or azienda.app_logo_url.endswith(".png"))

    def test_il_form_caricai_file(self):
        response = self.client.get(reverse("core:company_update"))
        self.assertContains(response, 'enctype="multipart/form-data"')

"""Test delle protezioni anti-abuso e degli allegati."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Product
from apps.core.models import UnitOfMeasure, VatRate

from .models import Attachment

User = get_user_model()

THROTTLE_LOGIN_3 = {"login": {"limit": 3, "window": 300}, "search": {"limit": 5, "window": 60}}
THROTTLE_SEARCH_5 = {"login": {"limit": 8, "window": 300}, "search": {"limit": 5, "window": 60}}


class AbuseThrottleTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(ABUSE_THROTTLE=THROTTLE_LOGIN_3)
    def test_blocco_dopo_troppi_tentativi_di_accesso(self):
        url = reverse("accounts:login")
        for _ in range(3):
            response = self.client.post(url, {"username": "utente", "password": "sbagliata"})
            self.assertEqual(response.status_code, 200)

        response = self.client.post(url, {"username": "utente", "password": "sbagliata"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Troppe richieste", response.content.decode("utf-8"))

    @override_settings(ABUSE_THROTTLE=THROTTLE_SEARCH_5)
    def test_blocco_ricerche_reiterate(self):
        user = User.objects.create_superuser("admin", "a@example.com", "password123!")
        self.client.force_login(user)
        url = reverse("contacts:search")

        for _ in range(5):
            response = self.client.get(url, {"q": "a"})
            self.assertEqual(response.status_code, 200)

        response = self.client.get(url, {"q": "a"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("application/json", response["Content-Type"])
        self.assertIn("error", response.json())

    @override_settings(ABUSE_THROTTLE=THROTTLE_SEARCH_5)
    def test_pagine_normali_non_bloccate(self):
        user = User.objects.create_superuser("admin", "a@example.com", "password123!")
        self.client.force_login(user)
        for _ in range(10):
            response = self.client.get(reverse("core:home"))
            self.assertEqual(response.status_code, 200)


class DashboardParamsTest(TestCase):
    def test_parametri_finestra_e_navigazione(self):
        user = User.objects.create_superuser("dash", "d@example.com", "password123!")
        self.client.force_login(user)
        for params in ("", "?finestra=1", "?finestra=3&indietro=2", "?finestra=6", "?finestra=12", "?finestra=99", "?indietro=-5", "?periodo=mese&finestra=3"):
            with self.subTest(params=params):
                response = self.client.get(reverse("core:home") + params)
                self.assertEqual(response.status_code, 200)


class AttachmentTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        cls.user = User.objects.create_superuser("allegati", "al@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.product = Product.objects.create(name="Pompa allegati", uom=cls.uom, sale_vat=cls.vat, purchase_vat=cls.vat)

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    def test_caricamento_su_articolo(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile("scheda.txt", b"contenuto tecnico", content_type="text/plain")
        response = self.client.post(
            reverse("core:attachment_upload"),
            {"product": self.product.pk, "file": upload, "name": "Scheda tecnica", "notes": "PDF fornitore"},
        )
        self.assertEqual(response.status_code, 302)
        attachment = Attachment.objects.get()
        self.assertEqual(attachment.product, self.product)
        self.assertEqual(attachment.name, "Scheda tecnica")
        self.assertEqual(attachment.uploaded_by, self.user)

        # la pagina articolo elenca l'allegato
        page = self.client.get(reverse("catalog:product_detail", args=[self.product.pk]))
        self.assertContains(page, "Scheda tecnica")

        # il file è protetto: anonimo → login
        file_url = attachment.file.url
        self.client.logout()
        response = self.client.get(file_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

        # autenticato → scarica
        self.client.force_login(self.user)
        response = self.client.get(file_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"contenuto tecnico")

    def test_eliminazione_allegato(self):
        self.client.force_login(self.user)
        attachment = Attachment.objects.create(
            product=self.product, file=SimpleUploadedFile("temporaneo.txt", b"x"), uploaded_by=self.user
        )
        response = self.client.post(reverse("core:attachment_delete", args=[attachment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attachment.objects.exists())

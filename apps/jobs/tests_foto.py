"""Test della rimozione dei seriali e della pagina foto dell'ufficio."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.contacts.models import Contact
from apps.core.models import Attachment
from apps.hr.models import Collaborator

from .models import Job

User = get_user_model()


class SerialiRimossiTest(TestCase):
    """I seriali non fanno più parte del gestionale."""

    def test_url_dei_seriali_non_esistono_piu(self):
        for nome in ("jobs:asset_list", "jobs:asset_create", "jobs:asset_update", "jobs:asset_delete"):
            with self.subTest(nome=nome):
                with self.assertRaises(NoReverseMatch):
                    reverse(nome, args=[1] if nome.endswith(("update", "delete")) else [])

    def test_il_modello_asset_non_esiste_piu(self):
        import apps.jobs.models as modelli

        self.assertFalse(hasattr(modelli, "Asset"))

    def test_il_menu_non_ha_la_voce_seriali(self):
        utente = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        self.client.force_login(utente)
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Seriali")

    def test_la_pagina_del_cantiere_non_ha_il_tab_seriali(self):
        utente = User.objects.create_superuser("admin2", "admin2@example.com", "password123!")
        cliente = Contact.objects.create(name="Cliente Cantiere", is_customer=True)
        cantiere = Job.objects.create(name="Cantiere senza seriali", customer=cliente)
        self.client.force_login(utente)
        response = self.client.get(reverse("jobs:job_detail", args=[cantiere.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "tab-assets")
        self.assertNotContains(response, "Registra seriale")


class FotoUfficioPermessiTest(TestCase):
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
        cls.cliente = Contact.objects.create(name="Cliente Permessi", is_customer=True)
        cls.collaboratore = Collaborator.objects.create(name="Foto Permessi")
        cls.cantiere = Job.objects.create(name="Cantiere permessi", customer=cls.cliente)
        cls.foto = Attachment.objects.create(
            name="Foto permessi",
            collaborator=cls.collaboratore,
            job=cls.cantiere,
            kind=Attachment.KIND_SITE,
            file=SimpleUploadedFile("foto.png", b"x", content_type="image/png"),
        )

    def test_personale_accede(self):
        utente = User.objects.create_user("hr", password="password123!")
        utente.groups.add(Group.objects.get(name="Personale"))
        self.client.force_login(utente)
        self.assertEqual(self.client.get(reverse("jobs:photo_list")).status_code, 200)

    def test_vendite_accede(self):
        utente = User.objects.create_user("sales", password="password123!")
        utente.groups.add(Group.objects.get(name="Vendite"))
        self.client.force_login(utente)
        self.assertEqual(self.client.get(reverse("jobs:photo_list")).status_code, 200)

    def test_magazzino_non_accede(self):
        utente = User.objects.create_user("warehouse", password="password123!")
        utente.groups.add(Group.objects.get(name="Magazzino"))
        self.client.force_login(utente)
        self.assertEqual(self.client.get(reverse("jobs:photo_list")).status_code, 403)

    def test_anonimo_va_al_login(self):
        response = self.client.get(reverse("jobs:photo_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

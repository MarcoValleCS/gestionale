"""Verifiche della pagina «Copia di sicurezza»."""
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class BackupTest(TestCase):
    def setUp(self):
        self.cartella = Path(tempfile.mkdtemp(prefix="backup-test-"))
        (self.cartella / "db_2026-10-03_0300.sql.gz").write_bytes(b"contenuto del database")
        (self.cartella / "media_2026-10-03_0300.tar.gz").write_bytes(b"foto")

        utenti = get_user_model()
        self.admin = utenti.objects.create_superuser("capo", "capo@example.com", "Password!234")
        self.venditore = utenti.objects.create_user("venditore", password="Password!234")

    @override_settings(BACKUP_ROOT=None)
    def test_solo_amministratori(self):
        self.client.force_login(self.venditore)
        risposta = self.client.get(reverse("core:backup"))
        self.assertEqual(risposta.status_code, 403)

    def test_elenco_backup(self):
        with override_settings(BACKUP_ROOT=self.cartella):
            self.client.force_login(self.admin)
            risposta = self.client.get(reverse("core:backup"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "db_2026-10-03_0300.sql.gz")
        self.assertContains(risposta, "media_2026-10-03_0300.tar.gz")

    def test_scaricamento(self):
        with override_settings(BACKUP_ROOT=self.cartella):
            self.client.force_login(self.admin)
            risposta = self.client.get(reverse("core:backup_download", args=["db_2026-10-03_0300.sql.gz"]))
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("attachment", risposta["Content-Disposition"])
        contenuto = b"".join(risposta.streaming_content)
        self.assertEqual(contenuto, b"contenuto del database")

    def test_niente_file_fuori_dalla_cartella(self):
        fuori = self.cartella.parent / "segreto.sql.gz"
        fuori.write_bytes(b"non si deve scaricare")
        with override_settings(BACKUP_ROOT=self.cartella):
            self.client.force_login(self.admin)
            risposta = self.client.get(reverse("core:backup_download", args=["..%2Fsegreto.sql.gz"]))
            risposta2 = self.client.get(reverse("core:backup_download", args=["segreto.sql.gz"]))
        self.assertEqual(risposta.status_code, 404)
        self.assertEqual(risposta2.status_code, 404)

    def test_cartella_assente_non_rompe_la_pagina(self):
        with override_settings(BACKUP_ROOT=Path(tempfile.mkdtemp()) / "non-esiste"):
            self.client.force_login(self.admin)
            risposta = self.client.get(reverse("core:backup"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Nessuna copia trovata")

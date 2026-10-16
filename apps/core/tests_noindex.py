"""Niente indicizzazione: intestazione e tag robots su tutte le pagine."""
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class NoIndexTest(TestCase):
    def test_intestazione_noindex_sulla_pagina_di_accesso(self):
        risposta = self.client.get("/accounts/login/")
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.headers.get("X-Robots-Tag"), "noindex, nofollow")

    def test_tag_robots_nella_pagina_di_accesso(self):
        risposta = self.client.get("/accounts/login/")
        self.assertContains(risposta, '<meta name="robots" content="noindex, nofollow">')

    def test_intestazione_e_tag_anche_dentro_il_gestionale(self):
        utente = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        self.client.force_login(utente)
        risposta = self.client.get("/")
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.headers.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertContains(risposta, '<meta name="robots" content="noindex, nofollow">')

    def test_termini_pubblici_senza_indicizzazione(self):
        """La pagina delle condizioni è pubblica: deve restare fuori dai motori."""
        risposta = self.client.get("/termini/")
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.headers.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertContains(risposta, '<meta name="robots" content="noindex, nofollow">')

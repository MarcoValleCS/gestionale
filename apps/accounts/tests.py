"""Test profilo utente: password ed email mittente."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ProfiloTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("mario", password="Password12345?", email="")
        self.client.force_login(self.user)

    def test_pagina_mostra_campo_email(self):
        pagina = self.client.get(reverse("accounts:password_change")).content.decode("utf-8")
        self.assertIn('name="email"', pagina)

    def test_cambio_email_senza_password(self):
        risposta = self.client.post(
            reverse("accounts:password_change"),
            {
                "email": "mario@aquaforma.it",
                "old_password": "Password12345?",
                "new_password1": "Password12345?",
                "new_password2": "Password12345?",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "mario@aquaforma.it")
        self.assertTrue(self.user.check_password("Password12345?"))

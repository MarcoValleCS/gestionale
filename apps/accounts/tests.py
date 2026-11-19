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
        self.assertIn('name="password_casella"', pagina)

    def test_cambio_email_senza_password(self):
        """L'email si cambia dal riquadro della casella, senza toccare la password di accesso."""
        risposta = self.client.post(
            reverse("accounts:casella_email"),
            {"azione": "salva", "email": "mario@aquaforma.it", "password_casella": ""},
        )
        self.assertEqual(risposta.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "mario@aquaforma.it")
        self.assertTrue(self.user.check_password("Password12345?"))
        self.assertFalse(self.user.ha_casella_personale)

    def test_cambio_password(self):
        risposta = self.client.post(
            reverse("accounts:password_change"),
            {"old_password": "Password12345?", "new_password1": "NuovaPassword987!", "new_password2": "NuovaPassword987!"},
        )
        self.assertEqual(risposta.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NuovaPassword987!"))

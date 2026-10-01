"""Test delle protezioni anti-abuso (tentativi di accesso e ricerche)."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

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

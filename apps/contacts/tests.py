"""Test di ricerca a digitazione e creazione rapida contatti."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Contact

User = get_user_model()


class ContactSearchTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.customer = Contact.objects.create(
            name="Rossi Costruzioni S.r.l.",
            is_customer=True,
            is_supplier=False,
            vat_number="01234567890",
            tax_code="01234567890",
            city="Milano",
        )
        cls.supplier = Contact.objects.create(
            name="Ferramenta Bianchi S.p.A.",
            is_customer=False,
            is_supplier=True,
            city="Torino",
        )
        cls.inactive = Contact.objects.create(name="Rossi Disattivato", is_customer=True, active=False)

    def setUp(self):
        self.client.force_login(self.user)

    def test_ricerca_cliente_per_nome(self):
        response = self.client.get(reverse("contacts:search"), {"q": "Rossi", "kind": "customer"})
        self.assertEqual(response.status_code, 200)
        labels = [row["label"] for row in response.json()["results"]]
        self.assertEqual(len(labels), 1)
        self.assertIn("Rossi Costruzioni", labels[0])
        self.assertIn(self.customer.code, labels[0])

    def test_ricerca_cliente_per_codice_fiscale(self):
        response = self.client.get(reverse("contacts:search"), {"q": "01234567890", "kind": "customer"})
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.customer.pk)
        self.assertIn("P.IVA", results[0]["extra"])

    def test_ricerca_fornitore_non_trova_clienti(self):
        response = self.client.get(reverse("contacts:search"), {"q": "Rossi", "kind": "supplier"})
        self.assertEqual(response.json()["results"], [])

        response = self.client.get(reverse("contacts:search"), {"q": "Ferramenta", "kind": "supplier"})
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.supplier.pk)

    def test_ricerca_esclude_disattivati(self):
        response = self.client.get(reverse("contacts:search"), {"q": "Rossi", "kind": "customer"})
        ids = [row["id"] for row in response.json()["results"]]
        self.assertNotIn(self.inactive.pk, ids)

    def test_creazione_rapida_salva_codice_fiscale(self):
        response = self.client.post(
            reverse("contacts:quick_create"),
            {
                "name": "Nuovo Cliente S.n.c.",
                "kind": "customer",
                "tax_code": "RSSMRA80A01H501U",
                "vat_number": "09876543210",
                "city": "Roma",
            },
        )
        self.assertEqual(response.status_code, 200)
        contact = Contact.objects.get(pk=response.json()["id"])
        self.assertEqual(contact.tax_code, "RSSMRA80A01H501U")
        self.assertEqual(contact.vat_number, "09876543210")
        self.assertTrue(contact.is_customer)

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


class ContactCreateTest(TestCase):
    """Creazione di un contatto dalla sezione Contatti (non dal documento)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")

    def setUp(self):
        self.client.force_login(self.user)

    def test_tutti_i_campi_obbligatori_sono_visibili_nella_pagina(self):
        """Regressione: un campo obbligatorio non disegnato blocca il salvataggio.

        Era il caso di «sconto abituale cliente»: il campo era obbligatorio nel
        form ma non compariva nella pagina, quindi il browser non lo inviava mai
        e il contatto non veniva salvato, senza mostrare alcun errore.
        """
        response = self.client.get(reverse("contacts:create"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        for nome, campo in form.fields.items():
            if campo.required:
                self.assertContains(
                    response,
                    f'name="{nome}"',
                    msg_prefix=f"il campo obbligatorio «{nome}» non è disegnato nella pagina",
                )

    def test_creazione_contatto_dalla_sezione(self):
        response = self.client.post(
            reverse("contacts:create"),
            {
                "name": "Idraulica Verdi S.r.l.",
                "is_customer": "on",
                "country": "Italia",
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 302, "il contatto deve essere salvato e si deve essere reindirizzati")
        contatto = Contact.objects.get(name="Idraulica Verdi S.r.l.")
        self.assertTrue(contatto.is_customer)
        self.assertEqual(contatto.code[:3], "CLI")

    def test_creazione_fornitore_dalla_sezione(self):
        response = self.client.post(
            reverse("contacts:create"),
            {
                "name": "Ricambi Blu S.p.A.",
                "is_supplier": "on",
                "country": "Italia",
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        contatto = Contact.objects.get(name="Ricambi Blu S.p.A.")
        self.assertTrue(contatto.is_supplier)
        self.assertEqual(contatto.code[:3], "FOR")

    def test_senza_cliente_ne_fornitore_non_salva(self):
        """Il contatto deve essere almeno cliente o fornitore."""
        response = self.client.post(
            reverse("contacts:create"),
            {"name": "Contatto Vuoto S.r.l.", "country": "Italia"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contact.objects.filter(name="Contatto Vuoto S.r.l.").exists())


class AgenziaContattoTest(TestCase):
    """La sezione Agenzia della scheda contatti."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.fornitore = Contact.objects.create(name="Fornitore Agenzia S.p.A.", is_customer=False, is_supplier=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_agenzia_salvata_dal_modulo(self):
        response = self.client.post(
            reverse("contacts:update", args=[self.fornitore.pk]),
            {
                "name": self.fornitore.name,
                "is_supplier": "on",
                "country": "Italia",
                "agent_name": "Mario Rossi",
                "agent_number": "AG-77",
                "agent_phone": "035 123456",
                "agent_email": "agente@agenzia.it",
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.fornitore.refresh_from_db()
        self.assertEqual(self.fornitore.agent_name, "Mario Rossi")
        self.assertEqual(self.fornitore.agent_number, "AG-77")
        self.assertEqual(self.fornitore.agent_phone, "035 123456")
        self.assertEqual(self.fornitore.agent_email, "agente@agenzia.it")
        self.assertTrue(self.fornitore.has_agency)

    def test_modulo_mostra_i_campi_dellagenzia(self):
        pagina = self.client.get(reverse("contacts:update", args=[self.fornitore.pk])).content.decode("utf-8")
        for campo in ("agent_name", "agent_number", "agent_phone", "agent_email"):
            self.assertIn(f'name="{campo}"', pagina)

    def test_scheda_mostra_la_sezione_agenzia(self):
        self.fornitore.agent_name = "Mario Rossi"
        self.fornitore.agent_email = "agente@agenzia.it"
        self.fornitore.save(update_fields=["agent_name", "agent_email"])
        pagina = self.client.get(reverse("contacts:detail", args=[self.fornitore.pk])).content.decode("utf-8")
        self.assertIn("Agenzia", pagina)
        self.assertIn("Mario Rossi", pagina)
        self.assertIn("agente@agenzia.it", pagina)

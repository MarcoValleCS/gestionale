"""Test della pipeline lead."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.contacts.models import Contact

from .models import Lead, LeadStage

User = get_user_model()


class LeadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.contatto = Contact.objects.create(name="Mario Rossi", is_customer=True)
        cls.gruppo, _ = Group.objects.get_or_create(name="Vendite")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_fasi_predefinite(self):
        self.assertEqual(LeadStage.objects.count(), 6)
        self.assertTrue(LeadStage.objects.filter(kind=LeadStage.KIND_WON).exists())
        self.assertTrue(LeadStage.objects.filter(kind=LeadStage.KIND_LOST).exists())

    def test_crea_lead_e_avanza_di_fase(self):
        prima = LeadStage.objects.filter(kind=LeadStage.KIND_OPEN).order_by("order").first()
        risposta = self.client.post(
            reverse("leads:lead_create"),
            {
                "name": "Rossi – piscina",
                "contact": self.contatto.pk,
                "phone": "3331112222",
                "stage": prima.pk,
                "owner": self.admin.pk,
                "estimated_value": "15000",
                "next_action": "2026-11-01",
                "source": "passaparola",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        lead = Lead.objects.get(name="Rossi – piscina")
        self.assertEqual(lead.estimated_value, 15000)

        risposta = self.client.post(reverse("leads:lead_stage", args=[lead.pk]), {"stage": "avanti"})
        self.assertEqual(risposta.status_code, 302)
        lead.refresh_from_db()
        self.assertNotEqual(lead.stage_id, prima.pk)
        self.assertGreater(lead.stage.order, prima.order)

    def test_bacheca(self):
        risposta = self.client.get(reverse("leads:board"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Contatto arrivato")
        self.assertContains(risposta, "Nuovo lead")

    def test_utente_vendite_accede_magazzino_no(self):
        vendite = User.objects.create_user("vendite", password="password123!")
        vendite.groups.add(self.gruppo)
        magazzino = User.objects.create_user("magazzino", password="password123!")

        self.client.force_login(vendite)
        self.assertEqual(self.client.get(reverse("leads:board")).status_code, 200)

        self.client.force_login(magazzino)
        self.assertEqual(self.client.get(reverse("leads:board")).status_code, 403)

    def test_fasi_solo_per_amministratori(self):
        vendite = User.objects.create_user("vendite2", password="password123!")
        vendite.groups.add(self.gruppo)
        self.client.force_login(vendite)
        self.assertEqual(self.client.get(reverse("leads:stage_list")).status_code, 403)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("leads:stage_list")).status_code, 200)

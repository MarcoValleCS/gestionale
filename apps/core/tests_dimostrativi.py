"""Test del comando che crea i dati dimostrativi."""
import shutil
import tempfile

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import CompanySettings
from apps.hr.models import Collaborator, CollaboratorTimeEntry, Employee, LeaveRequest, TimeEntry
from apps.purchasing.models import PurchaseOrder
from apps.sales import analytics
from apps.sales.models import Quote, SalesOrder

from .management.commands.dati_dimostrativi import ARTICOLI, PASSWORD_DEMO

Utente = get_user_model()


class DatiDimostrativiTest(TestCase):
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

    def crea(self, *args):
        return call_command("dati_dimostrativi", *args, verbosity=0)

    # ------------------------------------------------------------- creazione
    def test_crea_tutto_il_flusso_di_lavoro(self):
        self.crea()

        self.assertEqual(Product.objects.count(), len(ARTICOLI))
        self.assertGreaterEqual(Contact.objects.filter(is_customer=True).count(), 18)
        self.assertGreaterEqual(Contact.objects.filter(is_supplier=True).count(), 12)

        self.assertEqual(Quote.objects.count(), 16)
        # dopo la conversione i preventivi accettati diventano «convertiti»
        stati = set(Quote.objects.values_list("status", flat=True))
        self.assertTrue({"draft", "sent", "converted", "rejected"}.issubset(stati))

        self.assertTrue(SalesOrder.objects.exists())
        self.assertTrue(SalesOrder.objects.filter(status=SalesOrder.STATUS_DELIVERED).exists())
        self.assertTrue(SalesOrder.objects.filter(status=SalesOrder.STATUS_CONFIRMED).exists())
        self.assertTrue(PurchaseOrder.objects.exists())

        from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice

        self.assertTrue(DeliveryNote.objects.exists())
        self.assertTrue(SalesInvoice.objects.exists())
        self.assertTrue(PurchaseInvoice.objects.exists())

    def test_le_consegne_hanno_date_distribuite(self):
        """Le consegne sono sparse nei mesi: le statistiche hanno una storia."""
        self.crea()
        date_consegna = list(
            SalesOrder.objects.filter(status=SalesOrder.STATUS_DELIVERED).values_list("delivered_at", flat=True)
        )
        self.assertGreaterEqual(len(date_consegna), 3)
        mesi = {(d.year, d.month) for d in date_consegna}
        self.assertGreaterEqual(len(mesi), 2, f"tutte le consegne nello stesso mese: {mesi}")

    def test_le_giacenze_sono_caricate(self):
        self.crea()
        tracciati = list(Product.objects.filter(is_stock_tracked=True))
        self.assertTrue(tracciati)
        con_giacenza = [p for p in tracciati if p.total_stock > 0]
        # qualche articolo "su misura" resta a zero di proposito
        self.assertGreaterEqual(len(con_giacenza), len(tracciati) * 0.85)

    def test_margini_e_provvigioni_calcolabili(self):
        self.crea()
        summary = analytics.summary(analytics.PERIOD_12M)
        self.assertGreater(summary["revenue"], 0)
        self.assertGreater(summary["cost"], 0)
        self.assertGreater(summary["margin"], 0)

        # provvigioni dell'anno: ci sono sicuramente
        anno = analytics.commission_year()
        self.assertTrue(anno)
        self.assertGreater(sum(voce["commission"] for voce in anno), 0)

        # e anche nel mese corrente, così la pagina non è vuota
        mese = analytics.commission_report()
        self.assertGreater(mese["orders_count"], 0)
        self.assertGreater(mese["total_commission"], 0)

    def test_personale_e_collaboratori(self):
        self.crea()
        self.assertEqual(Employee.objects.count(), 4)
        self.assertTrue(TimeEntry.objects.exists())
        self.assertTrue(LeaveRequest.objects.exists())
        self.assertTrue(LeaveRequest.objects.filter(status=LeaveRequest.STATUS_REQUESTED).exists())
        self.assertTrue(LeaveRequest.objects.filter(status=LeaveRequest.STATUS_APPROVED).exists())
        self.assertEqual(Collaborator.objects.count(), 3)
        self.assertTrue(CollaboratorTimeEntry.objects.exists())
        # un collaboratore ha un utente collegato per provare l'area riservata
        self.assertTrue(Collaborator.objects.filter(user__isnull=False).exists())

    def test_utenti_demo_con_ruoli(self):
        self.crea()
        attesi = {
            "demo.vendite": "Vendite",
            "demo.acquisti": "Acquisti",
            "demo.magazzino": "Magazzino",
            "demo.ufficio": "Personale",
            "demo.collaboratore": "Collaboratore",
        }
        for username, gruppo in attesi.items():
            with self.subTest(username=username):
                utente = Utente.objects.get(username=username)
                self.assertEqual([g.name for g in utente.groups.all()], [gruppo])
                self.assertIsNotNone(authenticate(username=username, password=PASSWORD_DEMO))

    def test_azienda_configurata_e_con_logo(self):
        self.crea()
        azienda = CompanySettings.load()
        self.assertEqual(azienda.name, "Aquaforma srl")
        self.assertEqual(azienda.document_style, "moderno")
        self.assertTrue(azienda.theme_color)
        self.assertTrue(azienda.logo)

    def test_foto_generate(self):
        from apps.core.models import Attachment

        self.crea()
        self.assertTrue(Attachment.objects.filter(kind=Attachment.KIND_SITE).exists())
        self.assertTrue(Attachment.objects.filter(kind=Attachment.KIND_RECEIPT).exists())

    def test_modelli_di_preventivo(self):
        from apps.sales.models import QuoteTemplate

        self.crea()
        self.assertEqual(QuoteTemplate.objects.count(), 2)
        self.assertTrue(QuoteTemplate.objects.filter(name__startswith="Bagno").exists())

    # ---------------------------------------------------------------- reset
    def test_reset_conserva_utenti_e_dati_azienda(self):
        """Gli utenti veri e i dati azienda non devono sparire."""
        utente = Utente.objects.create_user("matteo", password="password123!")
        utente.groups.add(Group.objects.get(name="Vendite"))
        azienda = CompanySettings.load()
        azienda.name = "Aquaforma srl"
        azienda.vat_number = "04852690165"
        azienda.save()

        self.crea("--reset")

        utente.refresh_from_db()
        self.assertTrue(Utente.objects.filter(username="matteo").exists())
        self.assertEqual([g.name for g in utente.groups.all()], ["Vendite"])
        azienda.refresh_from_db()
        self.assertEqual(azienda.name, "Aquaforma srl")
        self.assertEqual(azienda.vat_number, "04852690165")

    def test_reset_cancella_i_dati_precedenti(self):
        cliente_vecchio = Contact.objects.create(name="Cliente Vecchio")
        Quote.objects.create(customer=cliente_vecchio)

        self.crea("--reset")

        self.assertFalse(Contact.objects.filter(name="Cliente Vecchio").exists())
        self.assertFalse(Quote.objects.filter(customer__name="Cliente Vecchio").exists())
        self.assertEqual(Quote.objects.count(), 16)

    def test_reset_su_dati_dimostrativi_non_lascia_residui(self):
        self.crea()
        primo_totale = Quote.objects.count()
        self.crea("--reset")
        self.assertEqual(Quote.objects.count(), primo_totale)
        self.assertEqual(Product.objects.count(), len(ARTICOLI))



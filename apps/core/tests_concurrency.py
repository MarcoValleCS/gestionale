"""Test di concorrenza: numerazione documenti e modifiche contemporanee.

Questi test verificano le protezioni che contano quando più utenti lavorano
insieme: numeri documento mai duplicati e nessuna sovrascrittura silenziosa
delle modifiche altrui.
"""
import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.sales.models import Quote

from .models import NumberSequence

User = get_user_model()


class NumberSequenceTest(TestCase):
    """La numerazione deve essere atomica a livello di database."""

    def test_incremento_eseguito_nel_database(self):
        """Il +1 deve avvenire in SQL: è questo che lo rende atomico.

        Con un incremento in Python due richieste leggerebbero lo stesso valore
        e scriverebbero lo stesso numero.
        """
        sequence = NumberSequence.get_for(NumberSequence.DOC_TYPE_QUOTE)
        with CaptureQueriesContext(connection) as ctx:
            sequence.take_next_number()
        sql = " ".join(" ".join(q["sql"].split()) for q in ctx.captured_queries)
        # L'incremento deve essere aritmetica SQL: "next_number" + 1
        self.assertRegex(
            sql,
            r'UPDATE .*"next_number" = \(.*"next_number" \+ 1\)',
            "l'incremento deve essere fatto in SQL, non in Python",
        )

    def test_numeri_progressivi_e_distinti(self):
        sequence = NumberSequence.get_for(NumberSequence.DOC_TYPE_QUOTE)
        numeri = [sequence.take_next_number() for _ in range(25)]
        self.assertEqual(len(set(numeri)), 25, "nessun numero deve ripetersi")
        self.assertEqual(numeri, sorted(numeri), "i numeri devono crescere")

    def test_contatore_avanzato_dopo_il_prelievo(self):
        sequence = NumberSequence.get_for(NumberSequence.DOC_TYPE_QUOTE)
        primo = sequence.take_next_number()
        sequence.refresh_from_db()
        secondo = sequence.take_next_number()
        self.assertNotEqual(primo, secondo)

    def test_numerazioni_separate_per_tipo_documento(self):
        preventivo = NumberSequence.get_for(NumberSequence.DOC_TYPE_QUOTE)
        ordine = NumberSequence.get_for(NumberSequence.DOC_TYPE_SALES_ORDER)
        preventivo.take_next_number()
        ordine.take_next_number()
        preventivo.refresh_from_db()
        ordine.refresh_from_db()
        # entrambe ripartono da 1: i contatori sono indipendenti
        self.assertEqual(preventivo.next_number, 2)
        self.assertEqual(ordine.next_number, 2)


class NumberSequenceConcurrencyTest(TransactionTestCase):
    """Con più richieste in parallelo i numeri non devono collidere."""

    reset_sequences = True

    def setUp(self):
        self.customer = Contact.objects.create(name="Cliente Concorrenza S.r.l.", is_customer=True)

    def test_creazioni_simultanee_producono_numeri_tutti_diversi(self):
        quanti = 5
        numeri = []
        errori = []
        barriera = threading.Barrier(quanti)
        lucchetto = threading.Lock()

        def crea_preventivo():
            try:
                barriera.wait(timeout=15)
                quote = Quote.objects.create(customer=self.customer)
                with lucchetto:
                    numeri.append(quote.number)
            except Exception as exc:  # noqa: BLE001 - vogliamo riportare qualsiasi errore
                with lucchetto:
                    errori.append(f"{type(exc).__name__}: {exc}")
            finally:
                connection.close()

        threads = [threading.Thread(target=crea_preventivo) for _ in range(quanti)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=45)

        self.assertEqual(errori, [], f"nessuna richiesta deve fallire: {errori}")
        self.assertEqual(len(numeri), quanti)
        self.assertEqual(len(set(numeri)), quanti, f"numeri duplicati: {sorted(numeri)}")


class ConflictAwareUpdateTest(TestCase):
    """Due utenti che modificano lo stesso documento non devono sovrascriversi."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.customer = Contact.objects.create(name="Cliente Conflitto S.r.l.", is_customer=True)
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat22 = VatRate.objects.get(code="22")
        cls.product = Product.objects.create(
            name="Articolo di prova",
            uom=cls.uom,
            sale_price=Decimal("10.00"),
            sale_vat=cls.vat22,
            purchase_price=Decimal("5.00"),
            purchase_vat=cls.vat22,
        )
        cls.quote = Quote.objects.create(customer=cls.customer, reference="Originale")

    def setUp(self):
        self.client.force_login(self.user)

    def url(self):
        return reverse("sales:quote_update", args=[self.quote.pk])

    def payload(self, reference):
        """Payload completo: il preventivo ha un formset per le righe."""
        return {
            "customer": self.customer.pk,
            "reference": reference,
            "status": Quote.STATUS_DRAFT,
            "date": "2026-10-01",
            "valid_until": "",
            "payment_term": "",
            "job": "",
            "terms_text": "",
            "notes": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": self.product.pk,
            "lines-0-description": "",
            "lines-0-qty": "1",
            "lines-0-uom": self.uom.pk,
            "lines-0-unit_price": "10.00",
            "lines-0-discount_pct": "0",
            "lines-0-vat_rate": self.vat22.pk,
        }

    def test_modifica_senza_concorrenza_va_a_buon_fine(self):
        self.client.get(self.url())  # apre la pagina
        response = self.client.post(self.url(), self.payload("Modificato da me"))
        self.assertEqual(response.status_code, 302)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.reference, "Modificato da me")

    def test_modifica_di_un_altro_utente_viene_rilevata(self):
        # L'utente apre la pagina di modifica...
        self.client.get(self.url())

        # ...nel frattempo un altro utente salva la stessa scheda
        self.quote.reference = "Salvato da un altro"
        self.quote.save()

        # ...e ora il primo utente prova a salvare i suoi dati
        response = self.client.post(self.url(), self.payload("Modificato da me"), follow=True)

        # Il salvataggio viene rifiutato e l'utente avvisato
        self.assertContains(response, "Un altro utente ha salvato")
        self.quote.refresh_from_db()
        self.assertEqual(
            self.quote.reference, "Salvato da un altro", "la modifica dell'altro utente non deve essere persa"
        )

    def test_il_conflitto_non_scrive_nulla(self):
        """Oltre a non sovrascrivere, il rifiuto non deve alterare altri campi."""
        self.client.get(self.url())
        self.quote.reference = "Salvato da un altro"
        self.quote.save()
        self.quote.refresh_from_db()
        prima = self.quote.updated_at

        self.client.post(self.url(), self.payload("Modificato da me"))

        self.quote.refresh_from_db()
        self.assertEqual(self.quote.reference, "Salvato da un altro")
        self.assertEqual(self.quote.updated_at, prima, "l'oggetto non deve essere stato toccato")

    def test_salvataggio_ripetuto_dallo_stesso_utente_non_e_un_conflitto(self):
        self.client.get(self.url())
        self.client.post(self.url(), self.payload("Prima modifica"))
        # secondo invio senza ricaricare la pagina: è sempre lo stesso utente
        response = self.client.post(self.url(), self.payload("Seconda modifica"))
        self.assertEqual(response.status_code, 302)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.reference, "Seconda modifica")

    def test_primo_salvataggio_senza_aver_aperto_la_pagina(self):
        """Chi invia i dati senza passare dalla pagina non va bloccato."""
        response = self.client.post(self.url(), self.payload("Diretto"))
        self.assertEqual(response.status_code, 302)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.reference, "Diretto")

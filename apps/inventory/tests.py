"""Test del magazzino: aggiornamento delle giacenze e concorrenza.

La giacenza è un dato condiviso: se due scarichi contemporanei leggessero la
stessa quantità e la riscrivessero, uno dei due andrebbe perso. Questi test
verificano che l'aggiornamento sia atomico a livello di database.
"""
import threading
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Product
from apps.core.models import UnitOfMeasure, VatRate

from .models import StockLevel, StockMovement, Warehouse
from .services import register_movement


class StockServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.warehouse = Warehouse.get_default()
        cls.product = Product.objects.create(
            name="Articolo magazzino",
            uom=cls.uom,
            sale_price=Decimal("10.00"),
            sale_vat=cls.vat,
            purchase_price=Decimal("5.00"),
            purchase_vat=cls.vat,
        )

    def level(self):
        return StockLevel.objects.get(product=self.product, warehouse=self.warehouse)

    def test_carico_aggiorna_la_giacenza(self):
        register_movement(product=self.product, delta=Decimal("10"), movement_type=StockMovement.TYPE_LOAD)
        self.assertEqual(self.level().quantity, Decimal("10"))

    def test_scarico_aggiorna_la_giacenza(self):
        register_movement(product=self.product, delta=Decimal("10"), movement_type=StockMovement.TYPE_LOAD)
        register_movement(product=self.product, delta=Decimal("-4"), movement_type=StockMovement.TYPE_UNLOAD)
        self.assertEqual(self.level().quantity, Decimal("6"))

    def test_movimenti_consecutivi_si_sommano(self):
        for _ in range(5):
            register_movement(product=self.product, delta=Decimal("3"), movement_type=StockMovement.TYPE_LOAD)
        self.assertEqual(self.level().quantity, Decimal("15"))
        self.assertEqual(StockMovement.objects.count(), 5)

    def test_scarico_oltre_la_giacenza_viene_rifiutato(self):
        register_movement(product=self.product, delta=Decimal("5"), movement_type=StockMovement.TYPE_LOAD)
        with self.assertRaises(ValidationError):
            register_movement(product=self.product, delta=Decimal("-8"), movement_type=StockMovement.TYPE_UNLOAD)
        # la giacenza non deve essere cambiata
        self.assertEqual(self.level().quantity, Decimal("5"))

    def test_scarico_oltre_la_giacenza_non_lascia_movimenti(self):
        register_movement(product=self.product, delta=Decimal("5"), movement_type=StockMovement.TYPE_LOAD)
        with self.assertRaises(ValidationError):
            register_movement(product=self.product, delta=Decimal("-8"), movement_type=StockMovement.TYPE_UNLOAD)
        self.assertEqual(StockMovement.objects.count(), 1, "il movimento rifiutato non deve essere registrato")

    def test_messaggio_di_errore_riporta_la_giacenza_disponibile(self):
        register_movement(product=self.product, delta=Decimal("5"), movement_type=StockMovement.TYPE_LOAD)
        with self.assertRaises(ValidationError) as ctx:
            register_movement(product=self.product, delta=Decimal("-8"), movement_type=StockMovement.TYPE_UNLOAD)
        self.assertIn("disponibili 5", str(ctx.exception))

    def test_giacenza_negativa_ammessa_se_richiesto(self):
        register_movement(
            product=self.product, delta=Decimal("-3"), movement_type=StockMovement.TYPE_UNLOAD, allow_negative=True
        )
        self.assertEqual(self.level().quantity, Decimal("-3"))

    def test_incremento_eseguito_nel_database(self):
        """Il calcolo deve avvenire in SQL: è ciò che lo rende atomico."""
        register_movement(product=self.product, delta=Decimal("7"), movement_type=StockMovement.TYPE_LOAD)
        with CaptureQueriesContext(connection) as ctx:
            register_movement(product=self.product, delta=Decimal("3"), movement_type=StockMovement.TYPE_LOAD)
        sql = " ".join(" ".join(q["sql"].split()) for q in ctx.captured_queries)
        self.assertRegex(
            sql,
            r'UPDATE "inventory_stocklevel" SET "quantity" = \(.*"inventory_stocklevel"\."quantity" \+',
            "la giacenza deve essere aggiornata con un UPDATE aritmetico, non con lettura + scrittura",
        )

    def test_movimento_a_zero_non_fa_nulla(self):
        self.assertIsNone(
            register_movement(product=self.product, delta=Decimal("0"), movement_type=StockMovement.TYPE_LOAD)
        )
        self.assertFalse(StockLevel.objects.exists())


class StockConcurrencyTest(TransactionTestCase):
    """Due scarichi in parallelo non devono perdere aggiornamenti."""

    reset_sequences = True

    def setUp(self):
        # TransactionTestCase svuota il database fra un test e l'altro: i dati
        # creati dalle migrazioni (unità di misura, IVA) non sono disponibili.
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code="PZ", defaults={"name": "Pezzi", "is_active": True}
        )
        self.vat, _ = VatRate.objects.get_or_create(
            code="22", defaults={"name": "IVA 22%", "rate": Decimal("22.00")}
        )
        self.warehouse, _ = Warehouse.objects.get_or_create(
            code="MAG", defaults={"name": "Magazzino principale", "is_default": True}
        )
        self.product = Product.objects.create(
            name="Articolo concorrenza",
            uom=self.uom,
            sale_price=Decimal("10.00"),
            sale_vat=self.vat,
            purchase_price=Decimal("5.00"),
            purchase_vat=self.vat,
        )
        register_movement(product=self.product, delta=Decimal("100"), movement_type=StockMovement.TYPE_LOAD)

    def test_scarichi_simultanei_non_perdono_quantita(self):
        quanti = 5
        scarico = Decimal("10")
        errori = []
        barriera = threading.Barrier(quanti)
        lucchetto = threading.Lock()

        def scarica():
            try:
                barriera.wait(timeout=15)
                register_movement(
                    product=self.product, delta=-scarico, movement_type=StockMovement.TYPE_UNLOAD
                )
            except Exception as exc:  # noqa: BLE001
                with lucchetto:
                    errori.append(f"{type(exc).__name__}: {exc}")
            finally:
                connection.close()

        threads = [threading.Thread(target=scarica) for _ in range(quanti)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=45)

        self.assertEqual(errori, [], f"nessuno scarico deve fallire: {errori}")
        level = StockLevel.objects.get(product=self.product, warehouse=self.warehouse)
        atteso = Decimal("100") - scarico * quanti
        self.assertEqual(
            level.quantity,
            atteso,
            "tutti gli scarichi devono essere contati: con una lettura non atomica se ne perderebbe qualcuno",
        )
        self.assertEqual(StockMovement.objects.filter(product=self.product).count(), quanti + 1)

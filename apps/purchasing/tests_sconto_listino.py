"""Sconto fornitore sul listino: mai applicato due volte.

Un listino importato da Odoo conteneva già i prezzi netti; applicandoci sopra
lo sconto del fornitore (68%) i costi d'acquisto sono finiti al 10% del
listino invece del 32%, e i margini dei preventivi sono risultati gonfiati.
"""
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.purchasing.models import PriceListItem, SupplierPriceList
from apps.purchasing.services import applica_sconto_listino, voci_gia_nette

User = get_user_model()


class ScontoListinoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.fornitore = Contact.objects.create(name="Box Doccia Srl", is_customer=False, is_supplier=True)
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")

    def _listino(self, prezzi):
        """Listino con un articolo per ogni (prezzo di vendita, prezzo della voce)."""
        listino = SupplierPriceList.objects.create(supplier=self.fornitore, name="Listino 2026")
        for indice, (vendita, prezzo) in enumerate(prezzi):
            articolo = Product.objects.create(
                code=f"BOX-{indice}", name=f"Box {indice}", uom=self.uom, sale_price=Decimal(vendita),
                sale_vat=self.vat, purchase_price=Decimal("0"), purchase_vat=self.vat, main_supplier=self.fornitore,
            )
            PriceListItem.objects.create(pricelist=listino, product=articolo, price=Decimal(prezzo))
        return listino

    def test_sconto_su_prezzi_lordi(self):
        listino = self._listino([("500", "500"), ("466", "466")])
        voci, aggiornati = applica_sconto_listino(listino, Decimal("68"))
        self.assertEqual((voci, aggiornati), (2, 2))
        self.assertEqual(Product.objects.get(code="BOX-0").purchase_price, Decimal("160.0000"))
        self.assertEqual(Product.objects.get(code="BOX-1").purchase_price, Decimal("149.1200"))
        self.assertEqual(set(listino.items.values_list("discount_pct", flat=True)), {Decimal("68.00")})

    def test_prezzi_gia_netti_rifiutati(self):
        listino = self._listino([("500", "160"), ("466", "149.12"), ("365", "116.80")])
        sospette, controllate = voci_gia_nette(listino, Decimal("68"))
        self.assertEqual((len(sospette), controllate), (3, 3))
        with self.assertRaises(ValidationError):
            applica_sconto_listino(listino, Decimal("68"))
        self.assertEqual(Product.objects.get(code="BOX-0").purchase_price, Decimal("0"), "nulla deve cambiare")
        self.assertEqual(set(listino.items.values_list("discount_pct", flat=True)), {Decimal("0.00")})

    def test_prezzi_netti_con_aumento_del_3_percento_rifiutati(self):
        listino = self._listino([("500", "164.80"), ("466", "153.59")])
        with self.assertRaises(ValidationError):
            applica_sconto_listino(listino, Decimal("68"))

    def test_forza_applica_comunque(self):
        listino = self._listino([("500", "160")])
        applica_sconto_listino(listino, Decimal("68"), forza=True)
        self.assertEqual(Product.objects.get(code="BOX-0").purchase_price, Decimal("51.2000"))

    def test_qualche_voce_scontata_non_blocca(self):
        """Un'offerta speciale su una voce sola non deve impedire lo sconto al listino."""
        listino = self._listino([("500", "500"), ("400", "400"), ("300", "90")])
        voci, _aggiornati = applica_sconto_listino(listino, Decimal("68"))
        self.assertEqual(voci, 3)

    def test_la_pagina_del_listino_rifiuta_con_un_messaggio(self):
        listino = self._listino([("500", "160"), ("466", "149.12")])
        self.client.force_login(self.admin)
        risposta = self.client.post(
            reverse("purchasing:pricelist_discount", args=[listino.pk]), {"percent": "68"}, follow=True
        )
        self.assertContains(risposta, "Sconto non applicato")
        self.assertEqual(Product.objects.get(code="BOX-0").purchase_price, Decimal("0"))

    def test_il_comando_rifiuta_senza_forza(self):
        self._listino([("500", "160"), ("466", "149.12")])
        with self.assertRaises(CommandError):
            call_command("prezzi_listini", "--sconto", "Box Doccia Srl", "68", stdout=StringIO())
        self.assertEqual(Product.objects.get(code="BOX-0").purchase_price, Decimal("0"))

    def test_il_comando_con_prezzi_lordi(self):
        self._listino([("500", "500")])
        uscita = StringIO()
        call_command("prezzi_listini", "--sconto", "Box Doccia Srl", "68", stdout=uscita)
        self.assertIn("prezzi di acquisto aggiornati: 1", uscita.getvalue())
        self.assertEqual(Product.objects.get(code="BOX-0").purchase_price, Decimal("160.0000"))

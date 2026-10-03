"""Verifiche che i moduli dei documenti restino leggeri.

Con migliaia di articoli in archivio, un menu che elenca tutto il catalogo
dentro ogni riga significa megabyte di pagina: qui si controlla che il modulo
renda solo la voce già scelta.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import CompanySettings, UnitOfMeasure, VatRate
from apps.sales.models import Quote, QuoteLine


class ModuloLeggeroTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        utenti = get_user_model()
        cls.utente = utenti.objects.create_user("venditore", password="Password!234")
        cls.utente.groups.add(*[])  # nessun ruolo: è superuser di prova sotto
        cls.utente.is_superuser = True
        cls.utente.save(update_fields=["is_superuser"])

        CompanySettings.load()
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.iva = VatRate.objects.get(code="22")
        cls.cliente = Contact.objects.create(name="Cliente Prova", is_customer=True)
        cls.articolo_scelto = Product.objects.create(
            name="Vaso scelto",
            code="SCELTO",
            uom=cls.uom,
            sale_vat=cls.iva,
            purchase_vat=cls.iva,
            purchase_price=Decimal("10.00"),
        )
        cls.altri = [
            Product.objects.create(
                name=f"Articolo {indice}", code=f"ALT{indice}", uom=cls.uom, sale_vat=cls.iva, purchase_vat=cls.iva
            )
            for indice in range(5)
        ]
        cls.preventivo = Quote.objects.create(customer=cls.cliente, created_by=cls.utente)
        QuoteLine.objects.create(
            quote=cls.preventivo, product=cls.articolo_scelto, description="Vaso", qty=Decimal("1"), unit_price=Decimal("20")
        )

    def setUp(self):
        self.client.force_login(self.utente)

    def test_il_menu_articolo_non_elenca_tutto_il_catalogo(self):
        risposta = self.client.get(reverse("sales:quote_update", args=[self.preventivo.pk]))
        self.assertEqual(risposta.status_code, 200)
        html = risposta.content.decode()
        # l'articolo della riga c'è (serve a non perdere il valore al salvataggio)
        self.assertIn("Vaso scelto", html)
        # gli altri articoli non devono viaggiare con la pagina
        for articolo in self.altri:
            self.assertNotIn(articolo.name, html, f"il modulo scarica anche {articolo.name}")

    def test_i_menu_di_unita_e_iva_ci_sono(self):
        risposta = self.client.get(reverse("sales:quote_create"))
        html = risposta.content.decode()
        self.assertIn("PZ – Pezzi", html)
        self.assertIn("IVA 22%", html)

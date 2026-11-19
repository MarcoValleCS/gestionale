"""Eliminazione di cantieri, contatti e articoli: solo se non c'è niente di collegato."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import KitComponent, Product
from apps.contacts.models import Contact
from apps.core.eliminazione import collegamenti, descrivi_collegamenti
from apps.core.models import ActivityLog, Attachment, Tag, UnitOfMeasure, VatRate
from apps.inventory.services import register_movement
from apps.jobs.models import Job
from apps.sales.models import Quote, QuoteLine

Utente = get_user_model()


class EliminazioneBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.vendite = Utente.objects.create_user("venditore", password="password123!")
        cls.vendite.groups.add(Group.objects.get(name="Vendite"))
        cls.magazzino = Utente.objects.create_user("magazziniere", password="password123!")
        cls.magazzino.groups.add(Group.objects.get(name="Magazzino"))
        cls.pz = UnitOfMeasure.objects.get(code="PZ")
        cls.iva = VatRate.objects.get(code="22")
        cls.cliente = Contact.objects.create(name="Cliente Cantieri srl", is_customer=True)

    def articolo(self, nome="Articolo libero", **extra):
        return Product.objects.create(
            name=nome, uom=self.pz, sale_price=Decimal("10"), sale_vat=self.iva,
            purchase_price=Decimal("5"), purchase_vat=self.iva, **extra,
        )

    def preventivo(self, **extra):
        return Quote.objects.create(customer=self.cliente, **extra)


class CollegamentiTest(EliminazioneBase):
    def test_elenco_dei_collegamenti(self):
        cantiere = Job.objects.create(name="Piscina Rossi", customer=self.cliente)
        self.assertEqual(collegamenti(cantiere), [])
        self.preventivo(job=cantiere)
        self.preventivo(job=cantiere)
        elenco = collegamenti(cantiere)
        self.assertEqual(elenco, [("Preventivi", 2)])
        self.assertEqual(descrivi_collegamenti(elenco), "2 preventivi")

    def test_le_etichette_non_bloccano(self):
        contatto = Contact.objects.create(name="Con etichetta", is_customer=True)
        contatto.tags.add(Tag.objects.create(name="VIP"))
        self.assertEqual(collegamenti(contatto), [])


class EliminaCantiereTest(EliminazioneBase):
    def test_cantiere_senza_collegamenti_si_elimina(self):
        cantiere = Job.objects.create(name="Creato per sbaglio", customer=self.cliente)
        self.client.force_login(self.vendite)
        pagina = self.client.get(reverse("jobs:job_detail", args=[cantiere.pk])).content.decode()
        self.assertIn(reverse("jobs:job_delete", args=[cantiere.pk]), pagina)
        risposta = self.client.post(reverse("jobs:job_delete", args=[cantiere.pk]))
        self.assertRedirects(risposta, reverse("jobs:job_list"))
        self.assertFalse(Job.objects.filter(pk=cantiere.pk).exists())
        self.assertTrue(
            ActivityLog.objects.filter(action="cancellato", object_id=str(cantiere.pk), model_name__icontains="cantiere").exists()
        )

    def test_cantiere_con_preventivo_non_si_elimina(self):
        cantiere = Job.objects.create(name="Con preventivo", customer=self.cliente)
        preventivo = self.preventivo(job=cantiere)
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse("jobs:job_detail", args=[cantiere.pk])).content.decode()
        self.assertIn("Non si può eliminare: è collegato a 1 preventivo", pagina)
        risposta = self.client.post(reverse("jobs:job_delete", args=[cantiere.pk]), follow=True)
        self.assertContains(risposta, "non si può eliminare")
        self.assertTrue(Job.objects.filter(pk=cantiere.pk).exists())
        preventivo.refresh_from_db()
        self.assertEqual(preventivo.job_id, cantiere.pk)

    def test_cantiere_con_foto_non_si_elimina(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        cantiere = Job.objects.create(name="Con foto", customer=self.cliente)
        Attachment.objects.create(
            job=cantiere, kind=Attachment.KIND_DOCUMENT, file=SimpleUploadedFile("nota.txt", b"testo", content_type="text/plain")
        )
        self.client.force_login(self.admin)
        self.client.post(reverse("jobs:job_delete", args=[cantiere.pk]))
        self.assertTrue(Job.objects.filter(pk=cantiere.pk).exists())

    def test_get_non_elimina(self):
        cantiere = Job.objects.create(name="Solo GET", customer=self.cliente)
        self.client.force_login(self.admin)
        self.client.get(reverse("jobs:job_delete", args=[cantiere.pk]))
        self.assertTrue(Job.objects.filter(pk=cantiere.pk).exists())

    def test_il_magazzino_non_elimina(self):
        cantiere = Job.objects.create(name="Protetto", customer=self.cliente)
        self.client.force_login(self.magazzino)
        self.assertEqual(self.client.post(reverse("jobs:job_delete", args=[cantiere.pk])).status_code, 403)
        self.assertTrue(Job.objects.filter(pk=cantiere.pk).exists())


class EliminaContattoTest(EliminazioneBase):
    def test_contatto_libero_si_elimina(self):
        contatto = Contact.objects.create(name="Doppione", is_customer=True)
        self.client.force_login(self.vendite)
        risposta = self.client.post(reverse("contacts:delete", args=[contatto.pk]))
        self.assertRedirects(risposta, reverse("contacts:list"))
        self.assertFalse(Contact.objects.filter(pk=contatto.pk).exists())

    def test_contatto_con_cantiere_o_preventivo_non_si_elimina(self):
        Job.objects.create(name="Lavoro", customer=self.cliente)
        self.preventivo()
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse("contacts:detail", args=[self.cliente.pk])).content.decode()
        self.assertIn("Non si può eliminare", pagina)
        risposta = self.client.post(reverse("contacts:delete", args=[self.cliente.pk]), follow=True)
        self.assertContains(risposta, "disattivalo")
        self.assertTrue(Contact.objects.filter(pk=self.cliente.pk).exists())

    def test_fornitore_di_un_articolo_non_si_elimina(self):
        fornitore = Contact.objects.create(name="Fornitore", is_supplier=True, is_customer=False)
        self.articolo(main_supplier=fornitore)
        self.client.force_login(self.admin)
        self.client.post(reverse("contacts:delete", args=[fornitore.pk]))
        self.assertTrue(Contact.objects.filter(pk=fornitore.pk).exists())


class EliminaArticoloTest(EliminazioneBase):
    def test_articolo_mai_usato_si_elimina_con_le_sue_parti(self):
        kit = self.articolo("Kit libero")
        componente = self.articolo("Componente")
        KitComponent.objects.create(kit=kit, component=componente, qty=Decimal("2"))
        self.client.force_login(self.vendite)
        risposta = self.client.post(reverse("catalog:product_delete", args=[kit.pk]))
        self.assertRedirects(risposta, reverse("catalog:product_list"))
        self.assertFalse(Product.objects.filter(pk=kit.pk).exists())
        # il componente resta: era usato dal kit, non ne faceva parte
        self.assertTrue(Product.objects.filter(pk=componente.pk).exists())

    def test_componente_di_un_kit_non_si_elimina(self):
        kit = self.articolo("Kit")
        componente = self.articolo("Componente usato")
        KitComponent.objects.create(kit=kit, component=componente, qty=Decimal("1"))
        self.client.force_login(self.admin)
        self.client.post(reverse("catalog:product_delete", args=[componente.pk]))
        self.assertTrue(Product.objects.filter(pk=componente.pk).exists())

    def test_articolo_in_un_preventivo_non_si_elimina(self):
        articolo = self.articolo("Venduto")
        preventivo = self.preventivo()
        QuoteLine.objects.create(
            quote=preventivo, product=articolo, description="x", qty=Decimal("1"), uom=self.pz,
            unit_price=Decimal("10"), vat_rate=self.iva,
        )
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse("catalog:product_detail", args=[articolo.pk])).content.decode()
        self.assertIn("Non si può eliminare", pagina)
        risposta = self.client.post(reverse("catalog:product_delete", args=[articolo.pk]), follow=True)
        self.assertContains(risposta, "non si può eliminare")
        self.assertTrue(Product.objects.filter(pk=articolo.pk).exists())

    def test_articolo_con_movimenti_non_si_elimina(self):
        articolo = self.articolo("A magazzino", is_stock_tracked=True)
        register_movement(product=articolo, delta=Decimal("3"), movement_type="load", user=self.admin)
        self.client.force_login(self.admin)
        self.client.post(reverse("catalog:product_delete", args=[articolo.pk]))
        self.assertTrue(Product.objects.filter(pk=articolo.pk).exists())

    def test_il_magazzino_non_elimina_articoli(self):
        articolo = self.articolo("Del magazzino")
        self.client.force_login(self.magazzino)
        self.assertEqual(self.client.post(reverse("catalog:product_delete", args=[articolo.pk])).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=articolo.pk).exists())

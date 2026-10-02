"""Test delle ore standard e delle foto caricate dai collaboratori."""
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.contacts.models import Contact
from apps.core.models import Attachment
from apps.jobs.models import Job

from .models import Collaborator, Employee, TimeEntry

User = get_user_model()


def immagine_png(larghezza=1800, altezza=1200, rumorosa=True):
    """Un PNG come quelli del telefono: se rumoroso occupa molto più del JPEG."""
    import os

    from PIL import Image

    buffer = BytesIO()
    if rumorosa:
        dati = os.urandom(larghezza * altezza * 3)
        Image.frombytes("RGB", (larghezza, altezza), dati).save(buffer, format="PNG")
    else:
        Image.new("RGB", (larghezza, altezza), (200, 120, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


class OreStandardTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.dipendente = Employee.objects.create(first_name="Luca", last_name="Bianchi")
        cls.cliente = Contact.objects.create(name="Cliente Ore", is_customer=True)
        cls.cantiere = Job.objects.create(name="Cantiere ore", customer=cls.cliente)

    def login(self, utente=None):
        self.client.force_login(utente or self.admin)

    def test_genera_solo_i_giorni_lavorativi(self):
        """Ottobre 2026: dal 1 al 31, i giorni feriali sono 22."""
        self.login()
        response = self.client.post(
            reverse("hr:timeentry_standard"),
            {
                "employee": self.dipendente.pk,
                "start_date": "2026-10-01",
                "end_date": "2026-10-31",
                "hours": "8",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": self.cantiere.pk,
                "description": "Giornata tipo",
            },
        )
        self.assertEqual(response.status_code, 302)
        registrazioni = TimeEntry.objects.filter(employee=self.dipendente)
        self.assertEqual(registrazioni.count(), 22)
        self.assertFalse(registrazioni.filter(date__week_day=1).exists())  # domenica
        self.assertFalse(registrazioni.filter(date__week_day=7).exists())  # sabato
        prima = registrazioni.order_by("date").first()
        self.assertEqual(prima.hours, Decimal("8.00"))
        self.assertEqual(prima.job, self.cantiere)
        self.assertEqual(prima.description, "Giornata tipo")
        self.assertEqual(prima.created_by, self.admin)

    def test_sabato_incluso_se_richiesto(self):
        self.login()
        self.client.post(
            reverse("hr:timeentry_standard"),
            {
                "employee": self.dipendente.pk,
                "start_date": "2026-10-01",
                "end_date": "2026-10-31",
                "hours": "6",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "",
                "include_saturday": "on",
            },
        )
        self.assertEqual(TimeEntry.objects.count(), 27)  # 22 feriali + 5 sabati di ottobre 2026

    def test_giornate_gia_registrate_lasciate_com_e(self):
        esistente = TimeEntry.objects.create(
            employee=self.dipendente, date=date(2026, 10, 5), hours=Decimal("4"), description="Mezza giornata"
        )
        self.login()
        self.client.post(
            reverse("hr:timeentry_standard"),
            {
                "employee": self.dipendente.pk,
                "start_date": "2026-10-01",
                "end_date": "2026-10-31",
                "hours": "8",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "",
            },
        )
        esistente.refresh_from_db()
        self.assertEqual(esistente.hours, Decimal("4"))
        self.assertEqual(esistente.description, "Mezza giornata")
        self.assertEqual(TimeEntry.objects.count(), 22)

    def test_sovrascrittura_se_richiesta(self):
        esistente = TimeEntry.objects.create(
            employee=self.dipendente, date=date(2026, 10, 5), hours=Decimal("4"), description="Mezza giornata"
        )
        self.login()
        self.client.post(
            reverse("hr:timeentry_standard"),
            {
                "employee": self.dipendente.pk,
                "start_date": "2026-10-01",
                "end_date": "2026-10-31",
                "hours": "8",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "Giornata intera",
                "overwrite": "on",
            },
        )
        esistente.refresh_from_db()
        self.assertEqual(esistente.hours, Decimal("8.00"))
        self.assertEqual(esistente.description, "Giornata intera")
        self.assertEqual(TimeEntry.objects.count(), 22)

    def test_periodo_rovesciato_non_registra_nulla(self):
        self.login()
        response = self.client.post(
            reverse("hr:timeentry_standard"),
            {
                "employee": self.dipendente.pk,
                "start_date": "2026-10-31",
                "end_date": "2026-10-01",
                "hours": "8",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TimeEntry.objects.exists())

    def test_tipo_straordinario(self):
        self.login()
        self.client.post(
            reverse("hr:timeentry_standard"),
            {
                "employee": self.dipendente.pk,
                "start_date": "2026-10-05",
                "end_date": "2026-10-06",
                "hours": "2",
                "kind": TimeEntry.KIND_OVERTIME,
                "job": "",
                "description": "Straordinari",
            },
        )
        self.assertEqual(TimeEntry.objects.filter(kind=TimeEntry.KIND_OVERTIME).count(), 2)

    def test_la_pagina_si_apre(self):
        self.login()
        response = self.client.get(reverse("hr:timeentry_standard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ore standard")

    def test_utente_senza_ruolo_non_accede(self):
        utente = User.objects.create_user("nessuno", password="password123!")
        self.login(utente)
        response = self.client.get(reverse("hr:timeentry_standard"))
        self.assertEqual(response.status_code, 403)


class CollaboratorPhotoTest(TestCase):
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

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.collab_user = User.objects.create_user("scavatore", password="password123!")
        cls.collab_user.groups.add(Group.objects.get(name="Collaboratore"))
        cls.ufficio = User.objects.create_user("ufficio", password="password123!")
        cls.ufficio.groups.add(Group.objects.get(name="Personale"))

        cls.cliente = Contact.objects.create(name="Cliente Foto", is_customer=True)
        cls.collaboratore = Collaborator.objects.create(name="Mario Scavi", user=cls.collab_user)
        cls.collega = Collaborator.objects.create(name="Altro Collaboratore")
        cls.cantiere = Job.objects.create(name="Piscina foto", customer=cls.cliente)

    def login(self, utente=None):
        self.client.force_login(utente or self.collab_user)

    def test_caricamento_foto_cantiere(self):
        self.login()
        response = self.client.post(
            reverse("hr:collaborator_photos"),
            {
                "kind": Attachment.KIND_SITE,
                "file": SimpleUploadedFile("cantiere.png", immagine_png(), content_type="image/png"),
                "job": self.cantiere.pk,
                "notes": "Inizio giornata",
            },
        )
        self.assertEqual(response.status_code, 302)
        foto = Attachment.objects.get()
        self.assertEqual(foto.collaborator, self.collaboratore)
        self.assertEqual(foto.kind, Attachment.KIND_SITE)
        self.assertEqual(foto.job, self.cantiere)
        self.assertEqual(foto.uploaded_by, self.collab_user)
        self.assertEqual(foto.notes, "Inizio giornata")
        # la foto è stata compressa in JPEG
        self.assertTrue(foto.file.name.endswith(".jpg"), foto.file.name)

    def test_caricamento_bolla_senza_cantiere(self):
        self.login()
        self.client.post(
            reverse("hr:collaborator_photos"),
            {
                "kind": Attachment.KIND_RECEIPT,
                "file": SimpleUploadedFile("bolla.pdf", b"%PDF-1.4 bolla", content_type="application/pdf"),
                "job": "",
                "notes": "Bolla ferramenta",
            },
        )
        bolla = Attachment.objects.get()
        self.assertEqual(bolla.kind, Attachment.KIND_RECEIPT)
        self.assertIsNone(bolla.job)
        self.assertTrue(bolla.file.name.endswith(".pdf"))

    def test_vede_solo_le_proprie_foto(self):
        Attachment.objects.create(
            name="Mia", collaborator=self.collaboratore, kind=Attachment.KIND_SITE,
            file=SimpleUploadedFile("mia.png", b"x", content_type="image/png"),
        )
        Attachment.objects.create(
            name="Altrui", collaborator=self.collega, kind=Attachment.KIND_SITE,
            file=SimpleUploadedFile("altrui.png", b"x", content_type="image/png"),
        )
        self.login()
        response = self.client.get(reverse("hr:collaborator_photos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mia")
        self.assertNotContains(response, "Altrui")

    def test_non_puo_cancellare_la_foto_di_un_altro(self):
        altrui = Attachment.objects.create(
            name="Altrui", collaborator=self.collega, kind=Attachment.KIND_SITE,
            file=SimpleUploadedFile("altrui.png", b"x", content_type="image/png"),
        )
        self.login()
        response = self.client.post(reverse("hr:collaborator_photo_delete", args=[altrui.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Attachment.objects.filter(pk=altrui.pk).exists())

    def test_puo_cancellare_la_propria(self):
        mia = Attachment.objects.create(
            name="Mia", collaborator=self.collaboratore, kind=Attachment.KIND_SITE,
            file=SimpleUploadedFile("mia.png", b"x", content_type="image/png"),
        )
        self.login()
        response = self.client.post(reverse("hr:collaborator_photo_delete", args=[mia.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attachment.objects.filter(pk=mia.pk).exists())

    def test_il_collaboratore_puo_raggiungere_la_sua_pagina_foto(self):
        """Il middleware non deve rimbalzare la pagina delle foto."""
        self.login()
        response = self.client.get(reverse("hr:collaborator_photos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Foto del cantiere")

    def test_il_collaboratore_non_vede_le_pagine_dell_ufficio(self):
        self.login()
        response = self.client.get(reverse("jobs:photo_list"))
        self.assertEqual(response.status_code, 302)

    def test_upload_senza_file_rifiutato(self):
        self.login()
        response = self.client.post(
            reverse("hr:collaborator_photos"),
            {"kind": Attachment.KIND_SITE, "job": "", "notes": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Attachment.objects.exists())


class FotoUfficioTest(TestCase):
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

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.cliente = Contact.objects.create(name="Cliente Ufficio", is_customer=True)
        cls.collaboratore = Collaborator.objects.create(name="Mario Scavi")
        cls.cantiere = Job.objects.create(name="Piscina ufficio", customer=cls.cliente)
        cls.foto = Attachment.objects.create(
            name="Foto mattina",
            collaborator=cls.collaboratore,
            job=cls.cantiere,
            kind=Attachment.KIND_SITE,
            notes="Inizio giornata",
            file=SimpleUploadedFile("foto.png", b"x", content_type="image/png"),
        )
        cls.bolla = Attachment.objects.create(
            name="Bolla ferramenta",
            collaborator=cls.collaboratore,
            kind=Attachment.KIND_RECEIPT,
            file=SimpleUploadedFile("bolla.pdf", b"%PDF", content_type="application/pdf"),
        )

    def login(self, utente=None):
        self.client.force_login(utente or self.admin)

    def test_elenco_foto(self):
        self.login()
        response = self.client.get(reverse("jobs:photo_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Foto mattina")
        self.assertContains(response, "Bolla ferramenta")
        self.assertContains(response, "Mario Scavi")

    def test_filtro_per_tipo(self):
        self.login()
        response = self.client.get(reverse("jobs:photo_list") + f"?tipo={Attachment.KIND_RECEIPT}")
        self.assertContains(response, "Bolla ferramenta")
        self.assertNotContains(response, "Foto mattina")

    def test_filtro_per_collaboratore(self):
        self.login()
        response = self.client.get(reverse("jobs:photo_list") + f"?collaboratore={self.collaboratore.pk}")
        self.assertContains(response, "Foto mattina")
        response = self.client.get(reverse("jobs:photo_list") + "?collaboratore=999999")
        self.assertNotContains(response, "Foto mattina")

    def test_filtro_per_cantiere(self):
        self.login()
        response = self.client.get(reverse("jobs:photo_list") + f"?cantiere={self.cantiere.pk}")
        self.assertContains(response, "Foto mattina")
        self.assertNotContains(response, "Bolla ferramenta")

    def test_eliminazione_dall_ufficio(self):
        self.login()
        response = self.client.post(reverse("jobs:photo_delete", args=[self.foto.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attachment.objects.filter(pk=self.foto.pk).exists())

    def test_le_foto_compaiono_nel_cantiere(self):
        self.login()
        response = self.client.get(reverse("jobs:job_detail", args=[self.cantiere.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Foto mattina")

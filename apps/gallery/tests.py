"""Test della galleria fotografica con etichette."""
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import GalleryPhoto, GalleryTag

User = get_user_model()


def foto_finta(nome="piscina.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (40, 30), (120, 120, 120)).save(buffer, format="JPEG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/jpeg")


class GalleryTest(TestCase):
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

    def setUp(self):
        self.client.force_login(self.admin)

    def test_carica_foto_con_etichette_nuove(self):
        risposta = self.client.post(
            reverse("gallery:photo_create"),
            {
                "title": "Piscina grigia con scala",
                "description": "Villa con scala ad angolo",
                "active": "on",
                "images": [foto_finta()],
                "new_tags": "piscina grigia, scala ad angolo",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        foto = GalleryPhoto.objects.get()
        self.assertEqual(foto.tags.count(), 2)
        self.assertTrue(foto.image.name.lower().endswith(".jpg"))
        self.assertEqual(GalleryTag.objects.count(), 2)

    def test_carica_piu_foto_insieme(self):
        risposta = self.client.post(
            reverse("gallery:photo_create"),
            {"title": "Piscine", "active": "on", "images": [foto_finta("a.jpg"), foto_finta("b.jpg")]},
        )
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(GalleryPhoto.objects.count(), 2)

    def test_filtro_per_etichette(self):
        foto1 = GalleryPhoto.objects.create(image=foto_finta(), title="Prima")
        foto2 = GalleryPhoto.objects.create(image=foto_finta("altra.jpg"), title="Seconda")
        grigia = GalleryTag.objects.create(name="piscina grigia")
        scala = GalleryTag.objects.create(name="scala ad angolo")
        foto1.tags.add(grigia, scala)
        foto2.tags.add(grigia)

        # con due etichette la foto deve averle entrambe
        risposta = self.client.get(reverse("gallery:photo_list"), {"tag": [grigia.pk, scala.pk]})
        ids = [foto.pk for foto in risposta.context["photos"]]
        self.assertIn(foto1.pk, ids)
        self.assertNotIn(foto2.pk, ids)

        # con una sola etichetta compaiono tutte quelle che la hanno
        risposta = self.client.get(reverse("gallery:photo_list"), {"tag": [grigia.pk]})
        ids = [foto.pk for foto in risposta.context["photos"]]
        self.assertIn(foto1.pk, ids)
        self.assertIn(foto2.pk, ids)

    def test_modifica_ed_eliminazione(self):
        foto = GalleryPhoto.objects.create(image=foto_finta(), title="Da modificare")
        nuova = GalleryTag.objects.create(name="piscina azzurra")

        risposta = self.client.post(
            reverse("gallery:photo_update", args=[foto.pk]),
            {"title": "Modificata", "active": "on", "tags": [nuova.pk]},
        )
        self.assertEqual(risposta.status_code, 302)
        foto.refresh_from_db()
        self.assertEqual(foto.title, "Modificata")
        self.assertEqual(list(foto.tags.all()), [nuova])

        risposta = self.client.post(reverse("gallery:photo_delete", args=[foto.pk]))
        self.assertEqual(risposta.status_code, 302)
        self.assertFalse(GalleryPhoto.objects.filter(pk=foto.pk).exists())

    def test_solo_chi_gestisce_carica(self):
        magazzino = User.objects.create_user("magazzino", password="password123!")
        gruppo, _ = Group.objects.get_or_create(name="Magazzino")
        magazzino.groups.add(gruppo)
        self.client.force_login(magazzino)

        self.assertEqual(self.client.get(reverse("gallery:photo_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("gallery:photo_create")).status_code, 403)

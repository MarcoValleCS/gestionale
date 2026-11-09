"""Rapportini dei collaboratori: invio dal cantiere, conferma, costi e rimborsi."""
import io
import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.contacts.models import Contact
from apps.core.models import Attachment
from apps.jobs.models import Job

from . import services
from .models import Collaborator, CollaboratorExpense, CollaboratorTimeEntry

User = get_user_model()


def immagine(nome="foto.png"):
    """Una piccola immagine PNG vera (le foto passano dalla compressione)."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/png")


def gestione_spese(totale=0, iniziali=0):
    return {
        "spese-TOTAL_FORMS": str(totale),
        "spese-INITIAL_FORMS": str(iniziali),
        "spese-MIN_NUM_FORMS": "0",
        "spese-MAX_NUM_FORMS": "1000",
    }


class RapportiniTestBase(TestCase):
    @classmethod
    def setUpClass(cls):
        # Prima di super(): i file creati in setUpTestData vanno nella cartella temporanea.
        cls._media = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.ufficio = User.objects.create_user("ufficio", password="password123!")
        cls.ufficio.groups.add(Group.objects.get(name="Personale"))
        cls.vendite = User.objects.create_user("vendite", password="password123!")
        cls.vendite.groups.add(Group.objects.get(name="Vendite"))
        cls.magazzino = User.objects.create_user("magazzino", password="password123!")
        cls.magazzino.groups.add(Group.objects.get(name="Magazzino"))

        cls.utente = User.objects.create_user("scavatore", password="password123!")
        cls.utente.groups.add(Group.objects.get(name="Collaboratore"))
        cls.collaboratore = Collaborator.objects.create(
            name="Mario Scavi", user=cls.utente, hourly_rate=Decimal("30.00")
        )
        cls.altro_utente = User.objects.create_user("elettricista", password="password123!")
        cls.altro_utente.groups.add(Group.objects.get(name="Collaboratore"))
        cls.collega = Collaborator.objects.create(name="Luca Fili", user=cls.altro_utente)

        cliente = Contact.objects.create(name="Cliente Piscina", is_customer=True)
        cls.cantiere = Job.objects.create(name="Piscina Rossi", customer=cliente)

    def rapportino(self, collaboratore=None, stato=CollaboratorTimeEntry.STATUS_SUBMITTED, ore="8", **campi):
        return CollaboratorTimeEntry.objects.create(
            collaborator=collaboratore or self.collaboratore,
            date=campi.pop("data", date(2026, 11, 3)),
            hours=Decimal(ore),
            job=campi.pop("job", self.cantiere),
            status=stato,
            **campi,
        )

    def spesa(self, entry, importo="12.50", **campi):
        return CollaboratorExpense.objects.create(entry=entry, amount=Decimal(importo), **campi)


class InvioDalCantiereTest(RapportiniTestBase):
    """Il collaboratore compila e invia il rapportino dal telefono."""

    def test_rapportino_completo_con_spese_scontrino_e_foto(self):
        self.client.force_login(self.utente)
        dati = {
            "date": "2026-11-03",
            "hours": "7.5",
            "job": self.cantiere.pk,
            "description": "Scavo vasca e reinterro",
            "notes": "Manca il tubo da 50",
            **gestione_spese(2),
            "spese-0-category": CollaboratorExpense.CATEGORY_MATERIAL,
            "spese-0-amount": "48.90",
            "spese-0-description": "Sacchi di cemento",
            "spese-0-supplier": "Brico",
            "spese-0-paid_by": CollaboratorExpense.PAID_BY_COLLABORATOR,
            "spese-0-scontrino": immagine("scontrino.png"),
            "spese-1-category": CollaboratorExpense.CATEGORY_MEAL,
            "spese-1-amount": "12",
            "spese-1-paid_by": CollaboratorExpense.PAID_BY_COMPANY,
            "foto": [immagine("inizio.png"), immagine("fine.png")],
        }
        risposta = self.client.post(reverse("hr:collaborator_entry_create"), dati)
        self.assertRedirects(risposta, reverse("hr:collaborator_area"))

        entry = CollaboratorTimeEntry.objects.get()
        self.assertEqual(entry.collaborator, self.collaboratore)
        self.assertEqual(entry.status, CollaboratorTimeEntry.STATUS_SUBMITTED)
        self.assertEqual(entry.hours, Decimal("7.5"))
        self.assertEqual(entry.notes, "Manca il tubo da 50")
        self.assertEqual(entry.created_by, self.utente)

        spese = list(entry.expenses.order_by("pk"))
        self.assertEqual([s.amount for s in spese], [Decimal("48.90"), Decimal("12.00")])
        self.assertIsNotNone(spese[0].receipt)
        self.assertEqual(spese[0].receipt.kind, Attachment.KIND_RECEIPT)
        self.assertEqual(spese[0].receipt.collaborator, self.collaboratore)
        self.assertIsNone(spese[1].receipt)

        foto = entry.attachments.filter(kind=Attachment.KIND_SITE)
        self.assertEqual(foto.count(), 2)
        self.assertTrue(all(f.job_id == self.cantiere.pk for f in foto))

    def test_il_collaboratore_scarica_il_proprio_scontrino(self):
        self.client.force_login(self.utente)
        self.client.post(
            reverse("hr:collaborator_entry_create"),
            {
                "date": "2026-11-03", "hours": "8", "job": self.cantiere.pk,
                **gestione_spese(1),
                "spese-0-category": "material", "spese-0-amount": "10", "spese-0-paid_by": "collaborator",
                "spese-0-scontrino": immagine("scontrino.png"),
            },
        )
        scontrino = CollaboratorExpense.objects.get().receipt
        self.assertEqual(self.client.get("/media/" + scontrino.file.name).status_code, 200)
        self.client.force_login(self.altro_utente)
        self.assertEqual(self.client.get("/media/" + scontrino.file.name).status_code, 404)

    def test_zero_ore_senza_spese_rifiutato(self):
        self.client.force_login(self.utente)
        risposta = self.client.post(
            reverse("hr:collaborator_entry_create"),
            {"date": "2026-11-03", "hours": "0", "job": self.cantiere.pk, **gestione_spese(0)},
        )
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "oppure aggiungi almeno una spesa")
        self.assertFalse(CollaboratorTimeEntry.objects.exists())

    def test_zero_ore_con_una_spesa_va_bene(self):
        self.client.force_login(self.utente)
        self.client.post(
            reverse("hr:collaborator_entry_create"),
            {
                "date": "2026-11-03", "hours": "0", "job": self.cantiere.pk,
                **gestione_spese(1),
                "spese-0-category": "material", "spese-0-amount": "30", "spese-0-paid_by": "collaborator",
            },
        )
        entry = CollaboratorTimeEntry.objects.get()
        self.assertEqual(entry.hours, Decimal("0"))
        self.assertEqual(entry.expenses.count(), 1)

    def test_riga_di_spesa_vuota_ignorata(self):
        """Una riga aggiunta e lasciata vuota non blocca l'invio."""
        self.client.force_login(self.utente)
        risposta = self.client.post(
            reverse("hr:collaborator_entry_create"),
            {
                "date": "2026-11-03", "hours": "8", "job": self.cantiere.pk,
                **gestione_spese(1),
                "spese-0-category": "material", "spese-0-amount": "", "spese-0-paid_by": "collaborator",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        self.assertFalse(CollaboratorExpense.objects.exists())

    def test_riga_tolta_dalla_pagina_ignorata(self):
        """«Togli» segna la riga nuova come eliminata: anche incompleta non blocca l'invio."""
        self.client.force_login(self.utente)
        risposta = self.client.post(
            reverse("hr:collaborator_entry_create"),
            {
                "date": "2026-11-03", "hours": "8", "job": self.cantiere.pk,
                **gestione_spese(2),
                "spese-0-category": "material", "spese-0-amount": "48.90", "spese-0-paid_by": "collaborator",
                "spese-1-amount": "3", "spese-1-DELETE": "on",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(list(CollaboratorExpense.objects.values_list("amount", flat=True)), [Decimal("48.90")])

    def test_la_pagina_del_modulo_si_apre(self):
        self.client.force_login(self.utente)
        risposta = self.client.get(reverse("hr:collaborator_entry_create"))
        self.assertContains(risposta, "Aggiungi spesa")
        self.assertContains(risposta, "spese-TOTAL_FORMS")

    def test_corregge_un_rapportino_rimandato_che_torna_in_coda(self):
        entry = self.rapportino(stato=CollaboratorTimeEntry.STATUS_REJECTED, review_note="Ore sbagliate")
        spesa = self.spesa(entry, "20")
        self.client.force_login(self.utente)
        pagina = self.client.get(reverse("hr:collaborator_entry_update", args=[entry.pk]))
        self.assertContains(pagina, "Ore sbagliate")
        self.client.post(
            reverse("hr:collaborator_entry_update", args=[entry.pk]),
            {
                "date": "2026-11-03", "hours": "6", "job": self.cantiere.pk,
                **gestione_spese(1, 1),
                "spese-0-id": spesa.pk, "spese-0-entry": entry.pk,
                "spese-0-category": "material", "spese-0-amount": "20", "spese-0-paid_by": "collaborator",
                "spese-0-DELETE": "on",
            },
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, CollaboratorTimeEntry.STATUS_SUBMITTED)
        self.assertEqual(entry.hours, Decimal("6"))
        self.assertIsNone(entry.reviewed_at)
        self.assertFalse(entry.expenses.exists(), "la spesa segnata va eliminata")

    def test_non_modifica_un_rapportino_confermato(self):
        entry = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        self.client.force_login(self.utente)
        risposta = self.client.post(
            reverse("hr:collaborator_entry_update", args=[entry.pk]),
            {"date": "2026-11-03", "hours": "1", "job": self.cantiere.pk},
        )
        self.assertRedirects(risposta, reverse("hr:collaborator_entry_detail", args=[entry.pk]))
        entry.refresh_from_db()
        self.assertEqual(entry.hours, Decimal("8"))

    def test_non_cancella_un_rapportino_confermato(self):
        entry = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        self.client.force_login(self.utente)
        self.client.post(reverse("hr:collaborator_entry_delete", args=[entry.pk]))
        self.assertTrue(CollaboratorTimeEntry.objects.filter(pk=entry.pk).exists())

    def test_cancellare_toglie_anche_foto_e_file(self):
        entry = self.rapportino()
        foto = Attachment.objects.create(
            file=immagine(), kind=Attachment.KIND_SITE, collaborator=self.collaboratore, report=entry
        )
        percorso = foto.file.path
        self.client.force_login(self.utente)
        self.client.post(reverse("hr:collaborator_entry_delete", args=[entry.pk]))
        self.assertFalse(CollaboratorTimeEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(Attachment.objects.filter(pk=foto.pk).exists())
        import os

        self.assertFalse(os.path.exists(percorso), "il file della foto va cancellato dal disco")

    def test_non_vede_il_rapportino_di_un_altro(self):
        altrui = self.rapportino(collaboratore=self.collega)
        self.client.force_login(self.utente)
        self.assertEqual(self.client.get(reverse("hr:collaborator_entry_detail", args=[altrui.pk])).status_code, 404)

    def test_non_entra_nelle_pagine_dell_ufficio(self):
        entry = self.rapportino()
        self.client.force_login(self.utente)
        for url in (reverse("hr:report_list"), reverse("hr:report_detail", args=[entry.pk]), reverse("hr:expense_reimbursements")):
            with self.subTest(url=url):
                risposta = self.client.get(url)
                self.assertEqual(risposta.status_code, 302)
                self.assertIn("/personale/mio-lavoro/", risposta["Location"])

    def test_l_area_mostra_stato_e_nota(self):
        self.rapportino(stato=CollaboratorTimeEntry.STATUS_REJECTED, description="Posa tubi", review_note="Manca la foto")
        self.client.force_login(self.utente)
        risposta = self.client.get(reverse("hr:collaborator_area"))
        self.assertContains(risposta, "Posa tubi")
        self.assertContains(risposta, "Da correggere")
        self.assertContains(risposta, "da correggere")


class ControlloUfficioTest(RapportiniTestBase):
    """L'ufficio conferma o rimanda i rapportini."""

    def test_coda_da_confermare(self):
        self.rapportino(description="In coda")
        self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED, data=date(2026, 11, 2), description="Già fatto")
        self.client.force_login(self.ufficio)
        risposta = self.client.get(reverse("hr:report_list"))
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(len(risposta.context["entries"]), 1)
        self.assertEqual(risposta.context["conteggi"]["da_confermare"], 1)

    def test_elenco_con_totale_spese_e_foto_senza_righe_doppie(self):
        entry = self.rapportino()
        self.spesa(entry, "10")
        self.spesa(entry, "5.50")
        for _ in range(3):
            Attachment.objects.create(file=immagine(), kind=Attachment.KIND_SITE, collaborator=self.collaboratore, report=entry)
        self.client.force_login(self.ufficio)
        voce = self.client.get(reverse("hr:report_list")).context["entries"][0]
        self.assertEqual(voce.totale_spese, Decimal("15.50"))
        self.assertEqual(voce.numero_foto, 3)

    def test_conferma_e_passa_al_successivo(self):
        primo = self.rapportino(data=date(2026, 11, 2))
        secondo = self.rapportino(data=date(2026, 11, 3))
        self.client.force_login(self.ufficio)
        risposta = self.client.post(reverse("hr:report_approve", args=[primo.pk]))
        self.assertRedirects(risposta, reverse("hr:report_detail", args=[secondo.pk]))
        primo.refresh_from_db()
        self.assertEqual(primo.status, CollaboratorTimeEntry.STATUS_APPROVED)
        self.assertEqual(primo.reviewed_by, self.ufficio)
        self.assertIsNotNone(primo.reviewed_at)

    def test_conferma_con_get_non_fa_nulla(self):
        entry = self.rapportino()
        self.client.force_login(self.ufficio)
        self.client.get(reverse("hr:report_approve", args=[entry.pk]))
        entry.refresh_from_db()
        self.assertEqual(entry.status, CollaboratorTimeEntry.STATUS_SUBMITTED)

    def test_doppia_conferma_rifiutata(self):
        entry = self.rapportino()
        copia = CollaboratorTimeEntry.objects.get(pk=entry.pk)
        services.conferma_rapportino(entry, self.ufficio)
        with self.assertRaises(ValidationError):
            services.conferma_rapportino(CollaboratorTimeEntry.objects.get(pk=copia.pk), self.ufficio)

    def test_rimandare_richiede_la_nota(self):
        entry = self.rapportino()
        self.client.force_login(self.ufficio)
        self.client.post(reverse("hr:report_reject", args=[entry.pk]), {"nota": ""})
        entry.refresh_from_db()
        self.assertEqual(entry.status, CollaboratorTimeEntry.STATUS_SUBMITTED)

    def test_rimanda_con_la_nota(self):
        entry = self.rapportino()
        self.client.force_login(self.ufficio)
        self.client.post(reverse("hr:report_reject", args=[entry.pk]), {"nota": "Scontrino illeggibile"})
        entry.refresh_from_db()
        self.assertEqual(entry.status, CollaboratorTimeEntry.STATUS_REJECTED)
        self.assertEqual(entry.review_note, "Scontrino illeggibile")

    def test_non_si_riapre_se_le_spese_sono_rimborsate(self):
        entry = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        spesa = self.spesa(entry)
        services.segna_rimborsate([spesa.pk], self.ufficio)
        with self.assertRaises(ValidationError):
            services.rimanda_rapportino(entry, self.ufficio, "Riapro")

    def test_le_vendite_non_confermano(self):
        entry = self.rapportino()
        self.client.force_login(self.vendite)
        self.assertEqual(self.client.get(reverse("hr:report_detail", args=[entry.pk])).status_code, 403)
        self.client.post(reverse("hr:report_approve", args=[entry.pk]))
        entry.refresh_from_db()
        self.assertEqual(entry.status, CollaboratorTimeEntry.STATUS_SUBMITTED)

    def test_pallino_nel_menu_per_il_personale(self):
        self.rapportino()
        self.client.force_login(self.ufficio)
        self.assertEqual(self.client.get(reverse("hr:report_list")).context["rapportini_da_confermare"], 1)
        self.client.force_login(self.vendite)
        self.assertEqual(self.client.get(reverse("core:home")).context["rapportini_da_confermare"], 0)


class RimborsiTest(RapportiniTestBase):
    def test_solo_spese_confermate_pagate_dal_collaboratore(self):
        confermato = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        da_rimborsare = self.spesa(confermato, "40")
        self.spesa(confermato, "99", paid_by=CollaboratorExpense.PAID_BY_COMPANY)
        in_attesa = self.rapportino(data=date(2026, 11, 4))
        self.spesa(in_attesa, "77")

        self.assertEqual(list(services.spese_da_rimborsare()), [da_rimborsare])
        self.client.force_login(self.ufficio)
        risposta = self.client.get(reverse("hr:expense_reimbursements"))
        self.assertEqual(risposta.context["grand_total"], Decimal("40"))

    def test_segna_rimborsate_solo_quelle_mostrate(self):
        confermato = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        mostrata = self.spesa(confermato, "40")
        arrivata_dopo = self.spesa(confermato, "15")
        self.client.force_login(self.ufficio)
        self.client.post(reverse("hr:expense_reimburse"), {"spesa": [mostrata.pk]})
        mostrata.refresh_from_db()
        arrivata_dopo.refresh_from_db()
        self.assertIsNotNone(mostrata.reimbursed_at)
        self.assertEqual(mostrata.reimbursed_by, self.ufficio)
        self.assertIsNone(arrivata_dopo.reimbursed_at)
        self.assertEqual(services.segna_rimborsate([mostrata.pk], self.ufficio), 0, "già rimborsata")

    def test_il_collaboratore_vede_quanto_gli_spetta(self):
        confermato = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        self.spesa(confermato, "40")
        self.client.force_login(self.utente)
        self.assertEqual(self.client.get(reverse("hr:collaborator_area")).context["to_reimburse"], Decimal("40"))


class CostiCantiereTest(RapportiniTestBase):
    def test_ore_e_spese_confermate_per_cantiere(self):
        entry = self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED, ore="8")
        self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED, ore="4", data=date(2026, 11, 4))
        self.spesa(entry, "48.90", category=CollaboratorExpense.CATEGORY_MATERIAL)
        self.spesa(entry, "12", category=CollaboratorExpense.CATEGORY_MEAL, paid_by=CollaboratorExpense.PAID_BY_COMPANY)
        attesa = self.rapportino(ore="10", data=date(2026, 11, 5))
        self.spesa(attesa, "500")
        self.rapportino(collaboratore=self.collega, stato=CollaboratorTimeEntry.STATUS_APPROVED, ore="5")

        costi = services.costi_collaboratori_cantiere(self.cantiere)
        self.assertEqual(costi["ore"], Decimal("17"))
        self.assertEqual(costi["costo_manodopera"], Decimal("360.00"), "12 ore × 30 €; il collega non ha tariffa")
        self.assertTrue(costi["senza_tariffa"])
        self.assertEqual(costi["totale_spese"], Decimal("60.90"), "il rapportino in attesa non conta")
        self.assertEqual(costi["totale"], Decimal("420.90"))
        self.assertEqual(costi["in_attesa"], 1)
        mario = next(r for r in costi["manodopera"] if r["collaboratore"] == "Mario Scavi")
        self.assertEqual((mario["ore"], mario["giornate"]), (Decimal("12"), 2))

    def test_la_scheda_cantiere_mostra_i_costi_all_ufficio(self):
        self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED)
        url = reverse("jobs:job_detail", args=[self.cantiere.pk])
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(url), "Costi dai rapportini")
        self.client.force_login(self.magazzino)
        risposta = self.client.get(url)
        self.assertEqual(risposta.status_code, 200)
        self.assertNotContains(risposta, "Costi dai rapportini")


class OreDallUfficioTest(RapportiniTestBase):
    def test_le_ore_esistenti_restano_nei_totali(self):
        self.rapportino(stato=CollaboratorTimeEntry.STATUS_APPROVED, ore="8", data=date(2026, 3, 2))
        self.assertEqual(self.collaboratore.hours_total(), Decimal("8"))
        self.assertEqual(self.collaboratore.hours_in_month(2026, 3), Decimal("8"))

    def test_l_elenco_ore_dell_ufficio_mostra_lo_stato(self):
        self.rapportino()
        self.client.force_login(self.ufficio)
        self.assertContains(self.client.get(reverse("hr:collaborator_time_list")), "Da confermare")

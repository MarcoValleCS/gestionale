"""Verifiche della guida del gestionale (wiki)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.accounts.permissions import ROLE_COLLABORATOR, ROLE_SALES, ROLE_WAREHOUSE
from apps.core.models import WikiPage


def crea_pagina(slug, titolo, ruoli="", area="Prova"):
    return WikiPage.objects.create(slug=slug, title=titolo, area=area, body="<p>Istruzioni di prova.</p>", roles=ruoli)


class GuidaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        utenti = get_user_model()
        cls.admin = utenti.objects.create_superuser("capo", "capo@example.com", "Password!234")

        gruppo_vendite, _ = Group.objects.get_or_create(name=ROLE_SALES)
        gruppo_magazzino, _ = Group.objects.get_or_create(name=ROLE_WAREHOUSE)
        gruppo_collaboratori, _ = Group.objects.get_or_create(name=ROLE_COLLABORATOR)

        cls.vendite = utenti.objects.create_user("venditore", password="Password!234")
        cls.vendite.groups.add(gruppo_vendite)

        cls.magazzino = utenti.objects.create_user("magazziniere", password="Password!234")
        cls.magazzino.groups.add(gruppo_magazzino)

        cls.collaboratore = utenti.objects.create_user("esterno", password="Password!234")
        cls.collaboratore.groups.add(gruppo_collaboratori)

        cls.per_tutti = crea_pagina("per-tutti", "Istruzioni generali")
        cls.per_vendite = crea_pagina("per-vendite", "Come fare un preventivo", ruoli=ROLE_SALES)
        cls.per_magazzino = crea_pagina("per-magazzino", "Come fare una rettifica", ruoli=ROLE_WAREHOUSE)
        cls.per_collaboratori = crea_pagina("per-collaboratori", "Ore e foto", ruoli=ROLE_COLLABORATOR)
        cls.nascosta = crea_pagina("nascosta", "Pagina non pubblicata")
        cls.nascosta.is_published = False
        cls.nascosta.save()

    def test_elenco_mostra_solo_le_pagine_del_proprio_ruolo(self):
        self.client.force_login(self.vendite)
        risposta = self.client.get(reverse("core:wiki"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Istruzioni generali")
        self.assertContains(risposta, "Come fare un preventivo")
        self.assertNotContains(risposta, "Come fare una rettifica")
        self.assertNotContains(risposta, "Pagina non pubblicata")

    def test_amministratore_vede_tutto(self):
        self.client.force_login(self.admin)
        risposta = self.client.get(reverse("core:wiki"))
        for titolo in ("Istruzioni generali", "Come fare un preventivo", "Come fare una rettifica", "Ore e foto"):
            self.assertContains(risposta, titolo)

    def test_pagina_di_un_altro_ruolo_non_e_accessibile(self):
        self.client.force_login(self.magazzino)
        risposta = self.client.get(reverse("core:wiki_page", args=["per-vendite"]))
        self.assertEqual(risposta.status_code, 404)
        # la sua, invece, si apre
        risposta = self.client.get(reverse("core:wiki_page", args=["per-magazzino"]))
        self.assertEqual(risposta.status_code, 200)

    def test_ricerca_nella_guida(self):
        self.client.force_login(self.vendite)
        risposta = self.client.get(reverse("core:wiki"), {"q": "preventivo"})
        self.assertContains(risposta, "Come fare un preventivo")
        self.assertNotContains(risposta, "Istruzioni generali")
        risposta = self.client.get(reverse("core:wiki"), {"q": "parola che non esiste"})
        self.assertContains(risposta, "Nessuna pagina trovata")

    def test_solo_lamministratore_modifica(self):
        self.client.force_login(self.vendite)
        risposta = self.client.get(reverse("core:wiki_edit", args=["per-tutti"]))
        self.assertEqual(risposta.status_code, 403)
        risposta = self.client.post(reverse("core:wiki_edit", args=["per-tutti"]), {"title": "Modificata", "area": "Prova", "body": "<p>x</p>"})
        self.assertEqual(risposta.status_code, 403)

    def test_amministratore_modifica_una_pagina(self):
        self.client.force_login(self.admin)
        risposta = self.client.post(
            reverse("core:wiki_edit", args=["per-tutti"]),
            {"title": "Istruzioni generali", "area": "Prova", "summary": "Sommario", "body": "<p>Testo aggiornato</p><script>alert(1)</script>", "roles": "", "order": 10, "is_published": "on"},
        )
        self.assertEqual(risposta.status_code, 302)
        pagina = WikiPage.objects.get(slug="per-tutti")
        self.assertIn("Testo aggiornato", pagina.body)
        self.assertNotIn("script", pagina.body.lower())
        self.assertEqual(pagina.updated_by, self.admin)

    def test_collaboratore_puo_leggere_la_sua_guida(self):
        self.client.force_login(self.collaboratore)
        risposta = self.client.get(reverse("core:wiki"))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Ore e foto")
        self.assertNotContains(risposta, "Come fare un preventivo")
        # la restrizione dei collaboratori non blocca la guida
        self.assertEqual(self.client.get(reverse("core:wiki_page", args=["per-collaboratori"])).status_code, 200)
        # ma il resto del gestionale resta precluso
        self.assertEqual(self.client.get(reverse("catalog:product_list")).status_code, 302)

    def test_la_pagina_mostra_le_altre_della_stessa_sezione(self):
        crea_pagina("seconda-vendite", "Come inviare un preventivo", ruoli=ROLE_SALES)
        self.client.force_login(self.vendite)
        risposta = self.client.get(reverse("core:wiki_page", args=["per-vendite"]))
        self.assertContains(risposta, "Come inviare un preventivo")


class ContenutiGuidaTest(TestCase):
    def test_le_pagine_del_programma_si_caricano(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("carica_guida", stdout=StringIO())
        self.assertGreaterEqual(WikiPage.objects.count(), 15)
        # ogni pagina ha titolo, sezione e contenuto
        for pagina in WikiPage.objects.all():
            self.assertTrue(pagina.title)
            self.assertTrue(pagina.area)
            self.assertTrue(pagina.body)
        # le pagine dei collaboratori sono visibili solo a loro
        collaboratori = WikiPage.objects.get(slug="il-mio-lavoro")
        self.assertEqual(collaboratori.elenco_ruoli, [ROLE_COLLABORATOR])

    def test_caricare_due_volte_non_duplica(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("carica_guida", stdout=StringIO())
        quante = WikiPage.objects.count()
        call_command("carica_guida", stdout=StringIO())
        self.assertEqual(WikiPage.objects.count(), quante)

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
        # le pagine dei collaboratori sono visibili a loro e all'amministratore
        collaboratori = WikiPage.objects.get(slug="il-mio-lavoro")
        self.assertEqual(collaboratori.elenco_ruoli, [ROLE_COLLABORATOR, "Amministratore"])

    def test_tutte_le_pagine_del_programma_hanno_slug_unici_e_contenuto(self):
        from apps.core.guida import PAGINE

        slug = [voce["slug"] for voce in PAGINE]
        self.assertEqual(len(slug), len(set(slug)))
        for voce in PAGINE:
            self.assertTrue(voce["title"])
            self.assertTrue(voce["area"])
            self.assertTrue(voce["body"])
            self.assertTrue(voce["summary"])
            self.assertIn(voce["area"], {
                "Generale", "Percorsi per ruolo", "Anagrafiche", "Vendite", "Acquisti",
                "Magazzino", "Cantieri", "Fatturazione", "Personale", "Collaboratori", "Impostazioni",
            })

    def test_le_guide_contengono_immagini_locali(self):
        from apps.core.guida import PAGINE

        self.assertTrue(any("/static/img/guida/" in voce["body"] for voce in PAGINE))

    def test_i_ruoli_delle_pagine_esistono(self):
        from apps.accounts.permissions import ALL_ROLES
        from apps.core.guida import PAGINE

        for voce in PAGINE:
            for ruolo in voce.get("roles", "").split(","):
                ruolo = ruolo.strip()
                if ruolo:
                    self.assertIn(ruolo, ALL_ROLES, voce["slug"])

    def test_le_immagini_citate_esistono(self):
        import re
        from pathlib import Path

        from django.conf import settings

        from apps.core.guida import PAGINE

        for voce in PAGINE:
            for nome in re.findall(r'<img[^>]+src="/static/img/guida/([^"]+)"', voce["body"]):
                percorso = Path(settings.BASE_DIR) / "static" / "img" / "guida" / nome
                self.assertTrue(percorso.is_file(), f"{voce['slug']}: manca {nome}")

    def test_immagini_esterne_rimosse_e_locali_ammesse(self):
        from apps.core.richtext import clean_guida

        html = clean_guida(
            '<img src="/static/img/guida/flusso-vendite.svg" alt="flusso">'
            '<img src="https://example.com/esterna.png" alt="esterna">'
        )
        self.assertIn("/static/img/guida/flusso-vendite.svg", html)
        self.assertNotIn("example.com", html)

    def test_il_comando_aggiorna_le_pagine_non_modificate(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("carica_guida", stdout=StringIO())
        pagina = WikiPage.objects.get(slug="primi-passi")
        pagina.body = "<p>Testo vecchio</p>"
        pagina.save()
        self.assertIsNone(pagina.updated_by)
        call_command("carica_guida", stdout=StringIO())
        pagina.refresh_from_db()
        self.assertIn("La dashboard", pagina.body)

    def test_il_comando_non_sovrascrive_le_pagine_modificate_a_mano(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("carica_guida", stdout=StringIO())
        admin = get_user_model().objects.create_superuser("altro-capo", "altro@example.com", "Password!234")
        pagina = WikiPage.objects.get(slug="primi-passi")
        pagina.body = "<p>Personalizzata</p>"
        pagina.updated_by = admin
        pagina.save()
        call_command("carica_guida", stdout=StringIO())
        pagina.refresh_from_db()
        self.assertEqual(pagina.body, "<p>Personalizzata</p>")
        call_command("carica_guida", aggiorna=True, stdout=StringIO())
        pagina.refresh_from_db()
        self.assertIn("La dashboard", pagina.body)

    def test_caricare_due_volte_non_duplica(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("carica_guida", stdout=StringIO())
        quante = WikiPage.objects.count()
        output = StringIO()
        call_command("carica_guida", stdout=output)
        self.assertEqual(WikiPage.objects.count(), quante)
        self.assertIn("0 aggiornate", output.getvalue())

    def test_tutte_le_pagine_si_aprono_per_un_amministratore(self):
        from io import StringIO

        from django.core.management import call_command
        from apps.core.guida import PAGINE

        call_command("carica_guida", stdout=StringIO())
        capo = get_user_model().objects.create_superuser("capo-guida", "guida@example.com", "Password!234")
        self.client.force_login(capo)
        for voce in PAGINE:
            risposta = self.client.get(reverse("core:wiki_page", args=[voce["slug"]]))
            self.assertEqual(risposta.status_code, 200, voce["slug"])

    def test_un_ruolo_non_vede_i_percorsi_degli_altri(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("carica_guida", stdout=StringIO())
        vendite = get_user_model().objects.create_user("venditore-guida", password="Password!234")
        vendite.groups.add(Group.objects.get_or_create(name=ROLE_SALES)[0])
        self.client.force_login(vendite)
        self.assertEqual(self.client.get(reverse("core:wiki_page", args=["percorso-vendite"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:wiki_page", args=["percorso-magazzino"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("core:wiki_page", args=["impostazioni"])).status_code, 404)

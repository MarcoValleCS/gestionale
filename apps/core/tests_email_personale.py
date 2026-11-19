"""Test di caselle email personali, email di invio predefinita e note predefinite."""
import smtplib
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.contacts.models import Contact
from apps.core import mailing
from apps.core.cifratura import cifra, decifra
from apps.core.models import CompanySettings, EmailInCoda, UnitOfMeasure, VatRate
from apps.sales.models import Quote, QuoteLine

Utente = get_user_model()
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def imposta_casella_aziendale(email="info@aquaforma.it", password="segreta-aziendale", nome="Aquaforma"):
    azienda = CompanySettings.load()
    azienda.mittente_nome = nome
    azienda.mittente_email = email
    azienda.imposta_password_smtp(password)
    azienda.save()
    return azienda


class BaseEmail(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.simone = Utente.objects.create_user(
            "simone", "simone@aquaforma.it", "password123!", first_name="Simone", last_name="Verdi"
        )
        cls.simone.groups.add(Group.objects.get(name="Vendite"))
        cls.katia = Utente.objects.create_user(
            "katia", "katia@aquaforma.it", "password123!", first_name="Katia", last_name="Neri"
        )
        cls.katia.groups.add(Group.objects.get(name="Vendite"))
        cls.cliente = Contact.objects.create(name="Cliente Email srl", is_customer=True, email="cliente@example.it")

    def casella_personale(self, utente, password="password-casella"):
        utente.imposta_password_casella(password)
        utente.save(update_fields=["password_email"])
        return utente


class CifraturaTest(TestCase):
    def test_andata_e_ritorno(self):
        testo = cifra("p4ssw0rd!àè")
        self.assertNotIn("p4ssw0rd", testo)
        self.assertEqual(decifra(testo), "p4ssw0rd!àè")

    def test_vuota_e_illeggibile(self):
        self.assertEqual(cifra(""), "")
        self.assertEqual(decifra(""), "")
        self.assertEqual(decifra("non-cifrato"), "")

    def test_si_rilegge_dopo_il_cambio_di_chiave_con_fallback(self):
        from django.conf import settings

        vecchia = settings.SECRET_KEY
        testo = cifra("segreta")
        with override_settings(SECRET_KEY="chiave-nuova-per-il-test", SECRET_KEY_FALLBACKS=[vecchia]):
            self.assertEqual(decifra(testo), "segreta")
        with override_settings(SECRET_KEY="chiave-nuova-per-il-test", SECRET_KEY_FALLBACKS=[]):
            self.assertEqual(decifra(testo), "")


@override_settings(EMAIL_BACKEND=LOCMEM)
class MittentePersonaleTest(BaseEmail):
    def test_password_salvata_cifrata(self):
        self.casella_personale(self.simone, "la-mia-password")
        self.simone.refresh_from_db()
        self.assertNotIn("la-mia-password", self.simone.password_email)
        self.assertEqual(self.simone.password_casella, "la-mia-password")
        self.assertTrue(self.simone.ha_casella_personale)

    def test_senza_password_si_usa_la_casella_aziendale(self):
        self.assertFalse(self.simone.ha_casella_personale)
        mittente = mailing.mittente_per(self.simone)
        self.assertFalse(mittente.personale)
        self.assertEqual(mittente.reply_to, "simone@aquaforma.it")

    def test_ognuno_spedisce_dalla_propria_casella(self):
        self.casella_personale(self.simone, "pw-simone")
        self.casella_personale(self.katia, "pw-katia")
        connessioni = []
        originale = mailing.get_connection

        def registra(*args, **kwargs):
            connessioni.append(kwargs)
            return originale(*args, **kwargs)

        for utente in (self.simone, self.katia):
            mailing.accoda_email(to_email="cliente@example.it", subject=f"Da {utente}", message="Testo", utente=utente)
        with mock.patch("apps.core.mailing.get_connection", side_effect=registra):
            call_command("invia_coda_email", stdout=mock.MagicMock())

        self.assertEqual(len(mail.outbox), 2)
        mittenti = sorted(email.from_email for email in mail.outbox)
        self.assertEqual(mittenti, ["Katia Neri <katia@aquaforma.it>", "Simone Verdi <simone@aquaforma.it>"])
        for email in mail.outbox:
            self.assertNotIn("Reply-To", email.extra_headers)
        credenziali = sorted((c["username"], c["password"]) for c in connessioni)
        self.assertEqual(credenziali, [("katia@aquaforma.it", "pw-katia"), ("simone@aquaforma.it", "pw-simone")])

    def test_password_rifiutata_parte_dalla_casella_aziendale(self):
        imposta_casella_aziendale()
        self.casella_personale(self.simone, "vecchia")
        voce = mailing.accoda_email(to_email="cliente@example.it", subject="Preventivo", message="Testo", utente=self.simone)
        originale = mailing._spedisci
        tentativi = []

        def spedisci(email, mittente):
            tentativi.append(mittente)
            if mittente.personale:
                raise smtplib.SMTPAuthenticationError(535, b"Authentication failed")
            return originale(email, mittente)

        with mock.patch("apps.core.mailing._spedisci", side_effect=spedisci):
            mailing.invia_voce_coda(voce)
        voce.refresh_from_db()
        self.assertEqual(voce.stato, EmailInCoda.STATO_INVIATA)
        self.assertIn("simone@aquaforma.it", voce.ultimo_errore)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Aquaforma <info@aquaforma.it>")
        self.assertEqual(mail.outbox[0].extra_headers.get("Reply-To"), "simone@aquaforma.it")

    def test_email_configurata_per_chi_ha_la_casella(self):
        self.assertFalse(mailing.email_configured())
        self.assertFalse(mailing.email_configured(self.simone))
        self.casella_personale(self.simone)
        self.assertTrue(mailing.email_configured(self.simone))
        self.assertFalse(mailing.email_configured(self.katia))

    @override_settings(EMAIL_HOST="smtps.pec.aruba.it", EMAIL_HOST_USER="aquaforma@pec.it", EMAIL_HOST_PASSWORD="pec")
    def test_le_caselle_personali_non_usano_il_server_pec(self):
        """Se nel .env c'è la PEC (per lo SDI), le caselle personali restano su Aruba."""
        self.casella_personale(self.simone)
        personale = mailing.mittente_per(self.simone)
        self.assertEqual((personale.host, personale.porta, personale.sicurezza), ("smtps.aruba.it", 465, "ssl"))
        self.assertEqual(personale.host_imap, "imaps.aruba.it")
        self.assertEqual(mailing.mittente_aziendale().host, "smtps.pec.aruba.it")

    def test_server_delle_caselle_personali_configurabile(self):
        azienda = CompanySettings.load()
        azienda.caselle_host = "smtp.example.it:2525"
        azienda.caselle_sicurezza = CompanySettings.SICUREZZA_TLS
        azienda.save()
        self.casella_personale(self.simone)
        personale = mailing.mittente_per(self.simone)
        self.assertEqual((personale.host, personale.porta, personale.sicurezza), ("smtp.example.it", 2525, "tls"))
        self.assertEqual(personale.host_imap, "imap.example.it")

    def test_copia_in_inviati_della_casella_personale(self):
        self.casella_personale(self.simone, "pw-simone")
        with (
            override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"),
            mock.patch("apps.core.mailing.get_connection") as connessione,
            mock.patch("apps.core.mailing.archivia_in_inviati") as archivia,
        ):
            connessione.return_value.send_messages.return_value = 1
            mailing.invia_subito(to_email="cliente@example.it", subject="Prova", message="x", utente=self.simone)
        self.assertEqual(connessione.call_args.args[0], mailing.BACKEND_SMTP)
        self.assertEqual(archivia.call_args.kwargs["casella"], ("simone@aquaforma.it", "pw-simone", "imaps.aruba.it"))

    def test_lo_sdi_parte_sempre_dalla_casella_aziendale(self):
        imposta_casella_aziendale()
        self.casella_personale(self.simone)
        voce = mailing.accoda_email(to_email="sdi01@pec.fatturapa.it", subject="SDI", message="xml")
        mailing.invia_voce_coda(voce)
        self.assertEqual(mail.outbox[0].from_email, "Aquaforma <info@aquaforma.it>")


@override_settings(EMAIL_BACKEND=LOCMEM)
class CasellaAziendaleTest(BaseEmail):
    def test_configurata_dalle_impostazioni(self):
        imposta_casella_aziendale()
        configurazione = mailing.configurazione_smtp()
        self.assertTrue(configurazione["configurata"])
        self.assertTrue(configurazione["da_impostazioni"])
        self.assertEqual(configurazione["utente"], "info@aquaforma.it")
        self.assertEqual(configurazione["password"], "segreta-aziendale")
        self.assertEqual(configurazione["host"], "smtps.aruba.it")
        self.assertEqual(configurazione["porta"], 465)
        self.assertEqual(configurazione["mittente"], "Aquaforma <info@aquaforma.it>")

    def test_senza_impostazioni_vale_il_file_env(self):
        from django.conf import settings

        configurazione = mailing.configurazione_smtp()
        self.assertFalse(configurazione["da_impostazioni"])
        self.assertEqual(configurazione["mittente"], settings.DEFAULT_FROM_EMAIL)

    @override_settings(EMAIL_HOST_USER="info@aquaforma.it", EMAIL_HOST_PASSWORD="dal-env", EMAIL_HOST="smtps.aruba.it")
    def test_stessa_casella_del_env_non_chiede_la_password(self):
        imposta_casella_aziendale(password="")
        configurazione = mailing.configurazione_smtp()
        self.assertTrue(configurazione["configurata"])
        self.assertEqual(configurazione["password"], "dal-env")

    def test_backend_smtp_vero_solo_per_le_caselle_del_gestionale(self):
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            self.assertEqual(mailing._backend(mailing.mittente_aziendale()), "django.core.mail.backends.console.EmailBackend")
            imposta_casella_aziendale()
            self.assertEqual(mailing._backend(mailing.mittente_aziendale()), mailing.BACKEND_SMTP)
        # nei test resta sempre locmem
        self.assertEqual(mailing._backend(mailing.mittente_aziendale()), LOCMEM)

    def test_pagina_salva_la_casella(self):
        self.client.force_login(self.admin)
        risposta = self.client.post(
            reverse("core:email_settings"),
            {
                "azione": "salva",
                "mittente_nome": "Aquaforma",
                "mittente_email": "info@aquaforma.it",
                "password": "nuova-segreta",
                "smtp_host": "",
                "smtp_porta": "",
                "smtp_sicurezza": "",
                "smtp_utente": "",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        azienda = CompanySettings.load()
        self.assertEqual(azienda.mittente_email, "info@aquaforma.it")
        self.assertNotIn("nuova-segreta", azienda.smtp_password)
        self.assertEqual(azienda.password_smtp, "nuova-segreta")
        pagina = self.client.get(reverse("core:email_settings")).content.decode()
        self.assertNotIn("nuova-segreta", pagina)
        self.assertIn("Password salvata", pagina)

    def test_pagina_chiede_la_password(self):
        self.client.force_login(self.admin)
        risposta = self.client.post(
            reverse("core:email_settings"),
            {"azione": "salva", "mittente_nome": "", "mittente_email": "info@aquaforma.it", "password": ""},
        )
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Inserisci la password della casella")
        self.assertEqual(CompanySettings.load().mittente_email, "")

    def test_pagina_password_vuota_tiene_quella_salvata(self):
        imposta_casella_aziendale(password="tenuta")
        self.client.force_login(self.admin)
        self.client.post(
            reverse("core:email_settings"),
            {"azione": "salva", "mittente_nome": "Nuovo nome", "mittente_email": "info@aquaforma.it", "password": ""},
        )
        azienda = CompanySettings.load()
        self.assertEqual(azienda.mittente_nome, "Nuovo nome")
        self.assertEqual(azienda.password_smtp, "tenuta")

    def test_prova_dalla_casella_aziendale(self):
        imposta_casella_aziendale()
        self.client.force_login(self.admin)
        risposta = self.client.post(reverse("core:email_settings"), {"azione": "prova", "to": "prova@example.it"})
        self.assertContains(risposta, "Email di prova inviata")
        self.assertEqual(mail.outbox[0].from_email, "Aquaforma <info@aquaforma.it>")

    def test_elenca_chi_ha_la_casella_personale(self):
        self.casella_personale(self.simone)
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse("core:email_settings")).content.decode()
        self.assertIn("Casella personale", pagina)
        self.assertIn("simone@aquaforma.it", pagina)


@override_settings(EMAIL_BACKEND=LOCMEM)
class ProfiloCasellaTest(BaseEmail):
    def test_salva_email_e_password(self):
        self.client.force_login(self.simone)
        risposta = self.client.post(
            reverse("accounts:casella_email"),
            {"azione": "salva", "email": "simone@aquaforma.it", "password_casella": "pw-simone"},
        )
        self.assertRedirects(risposta, reverse("accounts:password_change"))
        self.simone.refresh_from_db()
        self.assertEqual(self.simone.password_casella, "pw-simone")
        pagina = self.client.get(reverse("accounts:password_change")).content.decode()
        self.assertIn("partono da <strong>simone@aquaforma.it</strong>", pagina)
        self.assertNotIn("pw-simone", pagina)

    def test_salva_e_prova(self):
        self.client.force_login(self.simone)
        self.client.post(
            reverse("accounts:casella_email"),
            {"azione": "prova", "email": "simone@aquaforma.it", "password_casella": "pw-simone"},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["simone@aquaforma.it"])
        self.assertEqual(mail.outbox[0].from_email, "Simone Verdi <simone@aquaforma.it>")

    def test_password_senza_email_non_si_salva(self):
        self.client.force_login(self.simone)
        risposta = self.client.post(
            reverse("accounts:casella_email"), {"azione": "salva", "email": "", "password_casella": "pw"}
        )
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Indica l&#x27;email della casella")
        self.simone.refresh_from_db()
        self.assertEqual(self.simone.password_email, "")

    def test_cancella_password(self):
        self.casella_personale(self.simone)
        self.client.force_login(self.simone)
        self.client.post(
            reverse("accounts:casella_email"),
            {"azione": "salva", "email": "simone@aquaforma.it", "password_casella": "", "rimuovi_password_casella": "on"},
        )
        self.simone.refresh_from_db()
        self.assertFalse(self.simone.ha_casella_personale)

    def test_solo_post(self):
        self.client.force_login(self.simone)
        self.assertEqual(self.client.get(reverse("accounts:casella_email")).status_code, 405)

    def test_amministratore_imposta_la_casella_di_un_utente(self):
        self.client.force_login(self.admin)
        scheda = self.client.get(reverse("accounts:user_update", args=[self.katia.pk]))
        self.assertContains(scheda, 'name="password_casella"')
        self.assertNotContains(scheda, 'name="rimuovi_password_casella"')
        vendite = Group.objects.get(name="Vendite")
        risposta = self.client.post(
            reverse("accounts:user_update", args=[self.katia.pk]),
            {
                "username": "katia",
                "first_name": "Katia",
                "last_name": "Neri",
                "email": "katia@aquaforma.it",
                "phone": "",
                "groups": [vendite.pk],
                "is_active": "on",
                "new_password": "",
                "password_casella": "pw-katia",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        self.katia.refresh_from_db()
        self.assertEqual(self.katia.password_casella, "pw-katia")
        self.assertTrue(self.katia.check_password("password123!"))


@override_settings(EMAIL_BACKEND=LOCMEM)
class InvioDocumentoTest(BaseEmail):
    def preventivo(self):
        uom = UnitOfMeasure.objects.get(code="PZ")
        iva = VatRate.objects.get(code="22")
        preventivo = Quote.objects.create(customer=self.cliente)
        QuoteLine.objects.create(
            quote=preventivo, description="Posa", qty=Decimal("1"), uom=uom, unit_price=Decimal("100"), vat_rate=iva
        )
        preventivo.recalculate()
        return preventivo

    def test_preventivo_parte_dalla_casella_di_chi_lo_invia(self):
        self.casella_personale(self.simone, "pw-simone")
        preventivo = self.preventivo()
        self.client.force_login(self.simone)
        pagina = self.client.get(reverse("sales:quote_detail", args=[preventivo.pk])).content.decode()
        self.assertIn("Parte da <strong>simone@aquaforma.it</strong>", pagina)
        self.assertIn("(la tua casella)", pagina)

        self.client.post(
            reverse("sales:quote_email", args=[preventivo.pk]),
            {"to": "cliente@example.it", "subject": "Preventivo", "message": "Ecco il preventivo"},
        )
        voce = EmailInCoda.objects.get()
        self.assertEqual(voce.inviata_da, self.simone)
        call_command("invia_coda_email", stdout=mock.MagicMock())
        self.assertEqual(mail.outbox[0].from_email, "Simone Verdi <simone@aquaforma.it>")
        preventivo.refresh_from_db()
        self.assertEqual(preventivo.status, Quote.STATUS_SENT)

    def test_senza_casella_personale_mostra_quella_aziendale(self):
        imposta_casella_aziendale()
        preventivo = self.preventivo()
        self.client.force_login(self.katia)
        pagina = self.client.get(reverse("sales:quote_detail", args=[preventivo.pk])).content.decode()
        self.assertIn("Parte da <strong>info@aquaforma.it</strong>", pagina)
        self.assertIn("le risposte arrivano a katia@aquaforma.it", pagina)


class NotePredefiniteTest(BaseEmail):
    def test_default_iniziale_e_la_riga_dei_termini(self):
        from apps.core.termini_vendita import RIGA_TERMINI_BREVE

        self.assertEqual(CompanySettings.load().note_vendita, RIGA_TERMINI_BREVE)

    def test_le_note_salvate_finiscono_nei_nuovi_documenti(self):
        self.client.force_login(self.admin)
        risposta = self.client.post(
            reverse("core:note_predefinite"),
            {"note_vendita": "<b>Consegna in 30 giorni</b><script>alert(1)</script>", "note_acquisto": "Consegnare in magazzino"},
        )
        self.assertRedirects(risposta, reverse("core:note_predefinite"))
        azienda = CompanySettings.load()
        self.assertIn("Consegna in 30 giorni", azienda.note_vendita)
        self.assertNotIn("<script>", azienda.note_vendita)

        from apps.purchasing.forms import PurchaseOrderForm
        from apps.sales.forms import QuoteForm, SalesOrderForm

        self.assertIn("Consegna in 30 giorni", QuoteForm().fields["terms_text"].initial)
        self.assertIn("Consegna in 30 giorni", SalesOrderForm().fields["terms_text"].initial)
        self.assertEqual(PurchaseOrderForm().fields["notes"].initial, "Consegnare in magazzino")
        pagina = self.client.get(reverse("sales:quote_create")).content.decode()
        self.assertIn("Consegna in 30 giorni", pagina)

    def test_i_documenti_esistenti_non_cambiano(self):
        from apps.sales.forms import QuoteForm

        preventivo = Quote.objects.create(customer=self.cliente, terms_text="Note mie")
        azienda = CompanySettings.load()
        azienda.note_vendita = "Nuove note"
        azienda.save()
        self.assertEqual(QuoteForm(instance=preventivo).initial["terms_text"], "Note mie")

    def test_solo_amministratore(self):
        self.client.force_login(self.simone)
        self.assertEqual(self.client.get(reverse("core:note_predefinite")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("core:settings")), reverse("core:note_predefinite"))

    def test_pagina_mostra_l_editor(self):
        self.client.force_login(self.admin)
        risposta = self.client.get(reverse("core:note_predefinite"))
        self.assertContains(risposta, "rich-editor")
        self.assertContains(risposta, 'name="note_acquisto"')
        self.assertContains(risposta, "aquaforma.space/termini")


class PostaRimossaTest(BaseEmail):
    def test_la_posta_non_esiste_piu(self):
        with self.assertRaises(NoReverseMatch):
            reverse("core:posta")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/posta/").status_code, 404)
        self.assertNotContains(self.client.get(reverse("core:home")), "bi-inbox")

    def test_la_guida_ritira_la_pagina_della_posta(self):
        from io import StringIO

        from apps.core.models import WikiPage

        WikiPage.objects.create(slug="posta", title="Posta", body="<p>vecchia</p>")
        modificata = WikiPage.objects.create(slug="altra", title="Altra", body="<p>x</p>")
        call_command("carica_guida", stdout=StringIO())
        self.assertFalse(WikiPage.objects.filter(slug="posta").exists())
        self.assertTrue(WikiPage.objects.filter(slug="invio-email").exists())
        self.assertTrue(WikiPage.objects.filter(pk=modificata.pk).exists())

    def test_pagina_ritirata_modificata_a_mano_si_nasconde(self):
        from io import StringIO

        from apps.core.models import WikiPage

        pagina = WikiPage.objects.create(slug="posta", title="Posta", body="<p>mia</p>", updated_by=self.admin)
        call_command("carica_guida", stdout=StringIO())
        pagina.refresh_from_db()
        self.assertFalse(pagina.is_published)

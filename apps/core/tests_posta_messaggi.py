"""Test dei messaggi interni e della lettura della posta (IMAP simulato)."""
from email.message import EmailMessage
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.contacts.models import Contact

from .models import InboundEmail, InternalMessage

Utente = get_user_model()


def messaggio_email(oggetto="Richiesta informazioni", mittente="cliente@example.it", nome="Cliente Prova",
                    corpo="Buongiorno, vorrei un preventivo.", allegato=None, html=None, in_risposta=False,
                    immagine_incorporata=False):
    """Costruisce un'email vera, come quella che arriverebbe dalla casella."""
    messaggio = EmailMessage()
    messaggio["Subject"] = oggetto
    messaggio["From"] = f"{nome} <{mittente}>"
    messaggio["To"] = "showroom@aquaforma.it"
    messaggio["Date"] = "Fri, 03 Oct 2026 09:30:00 +0200"
    messaggio["Message-ID"] = "<prova@example.it>"
    if in_risposta:
        messaggio["In-Reply-To"] = "<precedente@aquaforma.it>"
        messaggio["References"] = "<precedente@aquaforma.it>"
    messaggio.set_content(corpo)
    if immagine_incorporata:
        messaggio.add_related(b"finta-immagine-png", maintype="image", subtype="png", cid="<logo@aquaforma>")
    if html:
        messaggio.add_alternative(html, subtype="html")
    if allegato:
        messaggio.add_attachment(allegato, maintype="application", subtype="pdf", filename="documento.pdf")
    return messaggio.as_bytes()


class FakeIMAP:
    """Finto server IMAP: restituisce le email preparate per il test."""

    def __init__(self, messaggi):
        self._messaggi = messaggi  # lista di bytes
        self.chiuso = False

    def login(self, utente, password):
        self.utente = utente
        self.password = password
        return "OK", [b"LOGIN completed"]

    def select(self, cartella, readonly=False):
        return "OK", [b"1"]

    def search(self, charset, criterio):
        numeri = b" ".join(str(i + 1).encode() for i in range(len(self._messaggi)))
        return "OK", [numeri]

    def fetch(self, numero, parti):
        corpo = self._messaggi[int(numero) - 1]
        return "OK", [(f"{numero} (RFC822)".encode(), corpo), b")"]

    def logout(self):
        self.chiuso = True
        return "BYE", [b"Logout"]


@override_settings(IMAP_HOST="imaps.example.it", IMAP_USER="posta@example.it",
                   IMAP_PASSWORD="segreta", IMAP_IS_CONFIGURED=True)
class PostaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.magazzino = Utente.objects.create_user("magazziniere", password="password123!")
        cls.magazzino.groups.add(Group.objects.get(name="Magazzino"))
        cls.cliente = Contact.objects.create(name="Cliente Prova srl", is_customer=True, email="cliente@example.it")

    def login(self, utente=None):
        self.client.force_login(utente or self.admin)

    def sincronizza(self, messaggi):
        finto = FakeIMAP(messaggi)
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=finto):
            from apps.core.imap import sincronizza

            esito = sincronizza()
        return esito, finto

    # ------------------------------------------------------------ scarico
    def test_le_email_vengono_scaricate_e_collegate_al_contatto(self):
        esito, finto = self.sincronizza([messaggio_email()])
        self.assertEqual(esito["nuove"], 1)
        self.assertEqual(esito["esaminate"], 1)
        self.assertTrue(finto.chiuso, "la connessione va chiusa")

        email_ricevuta = InboundEmail.objects.get()
        self.assertEqual(email_ricevuta.subject, "Richiesta informazioni")
        self.assertEqual(email_ricevuta.sender_email, "cliente@example.it")
        self.assertEqual(email_ricevuta.sender_name, "Cliente Prova")
        self.assertEqual(email_ricevuta.contact, self.cliente)
        self.assertFalse(email_ricevuta.body_loaded)

    def test_non_riscarica_le_email_gia_presenti(self):
        self.sincronizza([messaggio_email()])
        esito, _ = self.sincronizza([messaggio_email()])
        self.assertEqual(esito["nuove"], 0)
        self.assertEqual(InboundEmail.objects.count(), 1)

    def test_piu_email_insieme(self):
        esito, _ = self.sincronizza([
            messaggio_email(oggetto="Prima", mittente="uno@example.it"),
            messaggio_email(oggetto="Seconda", mittente="due@example.it"),
        ])
        self.assertEqual(esito["nuove"], 2)
        self.assertEqual(InboundEmail.objects.count(), 2)

    def test_senza_configurazione_avvisa(self):
        with override_settings(IMAP_IS_CONFIGURED=False):
            from apps.core.imap import PostaNonConfigurata, sincronizza

            with self.assertRaises(PostaNonConfigurata):
                sincronizza()

    # ------------------------------------------------------------ lettura
    def test_apertura_di_un_email_ne_scarica_il_corpo(self):
        self.sincronizza([messaggio_email(corpo="Buongiorno, vorrei un preventivo per il bagno.")])
        email_ricevuta = InboundEmail.objects.get()
        self.login()

        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([messaggio_email(corpo="Buongiorno, vorrei un preventivo per il bagno.")])):
            risposta = self.client.get(reverse("core:posta_messaggio", args=[email_ricevuta.pk]))

        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "vorrei un preventivo")
        email_ricevuta.refresh_from_db()
        self.assertTrue(email_ricevuta.body_loaded)
        self.assertTrue(email_ricevuta.is_read)

    def test_elenco_e_filtri(self):
        self.sincronizza([messaggio_email(oggetto="Prima"), messaggio_email(oggetto="Seconda")])
        self.login()
        risposta = self.client.get(reverse("core:posta") + "?filtro=tutte")
        self.assertContains(risposta, "Prima")
        self.assertContains(risposta, "Seconda")

        risposta = self.client.get(reverse("core:posta") + "?filtro=non_lette")
        self.assertContains(risposta, "Prima")

        risposta = self.client.get(reverse("core:posta") + "?filtro=tutte&q=Seconda")
        self.assertContains(risposta, "Seconda")
        self.assertNotContains(risposta, ">Prima<")

    def test_ricerca_per_mittente(self):
        self.sincronizza([messaggio_email(mittente="fornitore@example.it", nome="Fornitore")])
        self.login()
        self.assertContains(self.client.get(reverse("core:posta") + "?filtro=tutte&q=fornitore@"), "Fornitore")

    def test_scarico_dal_pulsante(self):
        self.login()
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([messaggio_email()])):
            risposta = self.client.post(reverse("core:posta_sincronizza"), follow=True)
        self.assertContains(risposta, "nuove email scaricate")
        self.assertEqual(InboundEmail.objects.count(), 1)

    # ----------------------------------------------------------- risposta
    @override_settings(EMAIL_IS_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_risposta_inviata(self):
        self.sincronizza([messaggio_email()])
        email_ricevuta = InboundEmail.objects.get()
        self.login()
        risposta = self.client.post(
            reverse("core:posta_rispondi", args=[email_ricevuta.pk]),
            {"body": "Buongiorno, le mando il preventivo."},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["cliente@example.it"])
        self.assertTrue(mail.outbox[0].subject.startswith("Re:"))
        self.assertContains(risposta, "Risposta inviata")

    def test_risposta_senza_testo_avvisa(self):
        self.sincronizza([messaggio_email()])
        email_ricevuta = InboundEmail.objects.get()
        self.login()
        risposta = self.client.post(reverse("core:posta_rispondi", args=[email_ricevuta.pk]), {"body": ""}, follow=True)
        self.assertContains(risposta, "Scrivi il testo della risposta")

    # ------------------------------------------------------------ allegati
    def test_allegato_scaricabile(self):
        self.sincronizza([messaggio_email(allegato=b"%PDF-1.4 finto")])
        email_ricevuta = InboundEmail.objects.get()
        self.login()
        dati = [messaggio_email(allegato=b"%PDF-1.4 finto")]

        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP(dati)):
            self.client.get(reverse("core:posta_messaggio", args=[email_ricevuta.pk]))
        email_ricevuta.refresh_from_db()
        self.assertEqual(len(email_ricevuta.attachments), 1)
        self.assertEqual(email_ricevuta.attachments[0]["nome"], "documento.pdf")

        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP(dati)):
            risposta = self.client.get(reverse("core:posta_allegato", args=[email_ricevuta.pk, 0]))
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("documento.pdf", risposta["Content-Disposition"])

    # -------------------------------------------------------------- permessi
    def test_il_magazziniere_non_vede_la_posta(self):
        self.login(self.magazzino)
        self.assertEqual(self.client.get(reverse("core:posta")).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        risposta = self.client.get(reverse("core:posta"))
        self.assertEqual(risposta.status_code, 302)


class MessaggiInterniTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.marco = Utente.objects.create_user("marco", "marco@example.com", "password123!", first_name="Marco", last_name="Rossi")
        cls.sara = Utente.objects.create_user("sara", "sara@example.com", "password123!", first_name="Sara", last_name="Bianchi")
        cls.estraneo = Utente.objects.create_user("estraneo", "estraneo@example.com", "password123!")

    def login(self, utente=None):
        self.client.force_login(utente or self.marco)

    def test_invio_di_un_messaggio(self):
        self.login()
        risposta = self.client.post(reverse("core:messaggi"), {"recipient": self.sara.pk, "body": "Ciao Sara!"})
        self.assertEqual(risposta.status_code, 302)
        messaggio = InternalMessage.objects.get()
        self.assertEqual(messaggio.sender, self.marco)
        self.assertEqual(messaggio.recipient, self.sara)
        self.assertFalse(messaggio.is_read)

    def test_la_conversazione_mostra_i_messaggi(self):
        InternalMessage.objects.create(sender=self.marco, recipient=self.sara, body="Ciao Sara")
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Ciao Marco")
        self.login()
        risposta = self.client.get(reverse("core:conversazione", args=[self.sara.pk]))
        self.assertContains(risposta, "Ciao Sara")
        self.assertContains(risposta, "Ciao Marco")

    def test_apertura_segna_come_letto(self):
        messaggio = InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Leggimi")
        self.login()
        self.client.get(reverse("core:conversazione", args=[self.sara.pk]))
        messaggio.refresh_from_db()
        self.assertTrue(messaggio.is_read)

    def test_il_pallino_dei_messaggi_non_letti(self):
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Uno")
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Due")
        self.login()
        risposta = self.client.get(reverse("core:home"))
        self.assertContains(risposta, "badge text-bg-danger ms-auto")
        self.assertEqual(risposta.context["messaggi_non_letti"], 2) if risposta.context else None

    def test_ognuno_vede_solo_le_sue_conversazioni(self):
        InternalMessage.objects.create(sender=self.marco, recipient=self.sara, body="Segreto tra noi")
        self.login(self.estraneo)
        risposta = self.client.get(reverse("core:messaggi"))
        self.assertNotContains(risposta, "Segreto tra noi")

    def test_non_si_puo_scrivere_a_se_stessi(self):
        self.login()
        risposta = self.client.post(reverse("core:messaggi"), {"recipient": self.marco.pk, "body": "Ciao me"})
        self.assertEqual(risposta.status_code, 200)
        self.assertFalse(InternalMessage.objects.exists())

    def test_risposta_dal_modulo_della_conversazione(self):
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Domanda")
        self.login()
        self.client.post(reverse("core:conversazione", args=[self.sara.pk]), {"body": "Risposta"})
        self.assertEqual(InternalMessage.objects.filter(sender=self.marco, recipient=self.sara, body="Risposta").count(), 1)

    def test_elenco_conversazioni_con_non_letti(self):
        InternalMessage.objects.create(sender=self.sara, recipient=self.marco, body="Uno")
        InternalMessage.objects.create(sender=self.marco, recipient=self.sara, body="Due")
        self.login()
        risposta = self.client.get(reverse("core:messaggi"))
        self.assertEqual(risposta.context["non_letti"], 1)
        self.assertEqual(len(risposta.context["conversazioni"]), 1)


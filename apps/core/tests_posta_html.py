"""Test del rendering delle email HTML e del filtro «solo posta rilevante»."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import InboundEmail
from .tests_posta_messaggi import FakeIMAP, messaggio_email

Utente = get_user_model()

CONFIGURAZIONE = dict(
    IMAP_HOST="imaps.example.it",
    IMAP_USER="posta@example.it",
    IMAP_PASSWORD="segreta",
    IMAP_IS_CONFIGURED=True,
    DOMINI_INTERNI={"aquaforma.it", "aquaforma.space"},
)


@override_settings(**CONFIGURAZIONE)
class ClassificazionePostaTest(TestCase):
    """Le newsletter restano fuori: si vedono solo risposte e posta aziendale."""

    def test_riconosce_le_risposte(self):
        from apps.core.imap import classifica

        for oggetto in ("Re: Preventivo 123", "R: Preventivo", "RE: Preventivo", "I: Preventivo",
                        "Rif: Preventivo", "AW: Preventivo"):
            with self.subTest(oggetto=oggetto):
                risposta, _interno, rilevante, motivo = classifica(oggetto, "cliente@example.it")
                self.assertTrue(risposta, oggetto)
                self.assertTrue(rilevante)
                self.assertEqual(motivo, "risposta")

    def test_riconosce_il_dominio_aziendale(self):
        from apps.core.imap import classifica

        risposta, interno, rilevante, motivo = classifica("Riunione di lunedì", "collega@aquaforma.it")
        self.assertFalse(risposta)
        self.assertTrue(interno)
        self.assertTrue(rilevante)
        self.assertEqual(motivo, "interno")

    def test_una_newsletter_non_e_rilevante(self):
        from apps.core.imap import classifica

        risposta, interno, rilevante, motivo = classifica("Sconti imperdibili!", "newsletter@negozio.it")
        self.assertFalse(risposta)
        self.assertFalse(interno)
        self.assertFalse(rilevante)
        self.assertEqual(motivo, "")

    def test_risposta_con_intestazione_in_reply_to(self):
        from apps.core.imap import classifica

        risposta, _interno, rilevante, _motivo = classifica("Preventivo", "cliente@example.it", in_risposta=True)
        self.assertTrue(risposta)
        self.assertTrue(rilevante)

    def test_le_email_vengono_classificate_allo_scarico(self):
        messaggi = [
            messaggio_email(oggetto="Re: Preventivo 123", mittente="cliente@example.it"),
            messaggio_email(oggetto="Newsletter di ottobre", mittente="promo@negozio.it"),
            messaggio_email(oggetto="Ordine interno", mittente="collega@aquaforma.it"),
        ]
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP(messaggi)):
            from apps.core.imap import sincronizza

            sincronizza()

        self.assertTrue(InboundEmail.objects.get(sender_email="cliente@example.it").is_relevant)
        self.assertFalse(InboundEmail.objects.get(sender_email="promo@negozio.it").is_relevant)
        self.assertTrue(InboundEmail.objects.get(sender_email="collega@aquaforma.it").is_relevant)

    def test_riclassifica_le_email_gia_scaricate(self):
        risposta_vecchia = InboundEmail.objects.create(
            uid="INBOX:1", subject="Re: Vecchia risposta", sender_email="cliente@example.it", is_relevant=True
        )
        pubblicita = InboundEmail.objects.create(
            uid="INBOX:2", subject="Pubblicità", sender_email="promo@negozio.it", is_relevant=True
        )

        from apps.core.imap import riclassifica

        riclassifica()
        risposta_vecchia.refresh_from_db()
        pubblicita.refresh_from_db()
        self.assertTrue(risposta_vecchia.is_relevant)
        self.assertEqual(risposta_vecchia.relevance, "risposta")
        self.assertFalse(pubblicita.is_relevant)
        self.assertEqual(pubblicita.relevance, "")


@override_settings(**CONFIGURAZIONE)
class FiltroPostaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        InboundEmail.objects.create(uid="INBOX:1", subject="Re: Preventivo", sender_email="cliente@example.it",
                                    is_reply=True, is_relevant=True, relevance="risposta")
        InboundEmail.objects.create(uid="INBOX:2", subject="Newsletter", sender_email="promo@negozio.it")
        InboundEmail.objects.create(uid="INBOX:3", subject="Nota interna", sender_email="collega@aquaforma.it",
                                    is_internal=True, is_relevant=True, relevance="interno")

    def login(self):
        self.client.force_login(self.admin)

    def test_elenco_predefinito_solo_rilevanti(self):
        self.login()
        risposta = self.client.get(reverse("core:posta"))
        self.assertContains(risposta, "Re: Preventivo")
        self.assertContains(risposta, "Nota interna")
        self.assertNotContains(risposta, "Newsletter")

    def test_filtro_tutte_mostra_anche_le_newsletter(self):
        self.login()
        risposta = self.client.get(reverse("core:posta") + "?filtro=tutte")
        self.assertContains(risposta, "Newsletter")

    def test_i_conteggi_dei_filtri(self):
        self.login()
        risposta = self.client.get(reverse("core:posta"))
        self.assertEqual(risposta.context["conteggi"]["tutte"], 3)
        self.assertEqual(risposta.context["conteggi"]["rilevanti"], 2)

    def test_pallino_della_posta_non_letta(self):
        self.login()
        risposta = self.client.get(reverse("core:home"))
        self.assertContains(risposta, "/posta/")
        self.assertEqual(risposta.context["posta_non_lette"], 2)


@override_settings(**CONFIGURAZIONE)
class RenderingHtmlEmailTest(TestCase):
    """Le email HTML devono restare leggibili: tabelle, link e immagini."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")

    def login(self):
        self.client.force_login(self.admin)

    def test_il_corpo_html_mantiene_la_grafica(self):
        html = (
            "<html><body>"
            "<table><tr><td style='background-color:#eee; padding:10px'>"
            "<h2>Preventivo richiesto</h2>"
            "<p>Ciao, <strong>confermo</strong> l'ordine.</p>"
            "<a href='https://aquaforma.space'>Il nostro sito</a>"
            "</td></tr></table>"
            "<script>alert('ciao')</script>"
            "</body></html>"
        )
        dati = messaggio_email(html=html, corpo="versione testo")
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([dati])):
            from apps.core.imap import sincronizza

            sincronizza()

        email_ricevuta = InboundEmail.objects.get()
        self.login()
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([dati])):
            risposta = self.client.get(reverse("core:posta_messaggio", args=[email_ricevuta.pk]))

        contenuto = risposta.content.decode()
        self.assertIn("<table", contenuto)
        self.assertIn("<h2", contenuto)
        self.assertIn("background-color", contenuto)
        self.assertIn("https://aquaforma.space", contenuto)
        self.assertNotIn("alert(", contenuto, "lo script dell'email non deve finire in pagina")
        self.assertNotIn("&lt;table", contenuto, "l'HTML non deve finire in pagina come testo")
        # lo script dell'email viene tolto: nella pagina restano solo quelli del gestionale
        corpo_email = contenuto.split('class="email-body"')[1].split("</div>")[0]
        self.assertNotIn("<script", corpo_email)

    def test_le_immagini_incorporate_si_vedono(self):
        html = "<p>Ecco il logo: <img src='cid:logo@aquaforma' alt='logo'></p>"
        dati = messaggio_email(html=html, immagine_incorporata=True, corpo="testo")
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([dati])):
            from apps.core.imap import sincronizza

            sincronizza()

        email_ricevuta = InboundEmail.objects.get()
        self.login()
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([dati])):
            risposta = self.client.get(reverse("core:posta_messaggio", args=[email_ricevuta.pk]))
        contenuto = risposta.content.decode()
        self.assertIn(f"/posta/{email_ricevuta.pk}/allegato/0/", contenuto)
        self.assertNotIn("cid:", contenuto)

    def test_gli_allegati_veri_restano_scaricabili(self):
        dati = messaggio_email(html="<p>ciao</p>", allegato=b"%PDF-1.4 finto",
                               immagine_incorporata=True, corpo="testo")
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([dati])):
            from apps.core.imap import sincronizza

            sincronizza()
        email_ricevuta = InboundEmail.objects.get()
        self.login()
        with mock.patch("apps.core.imap.imaplib.IMAP4_SSL", return_value=FakeIMAP([dati])):
            risposta = self.client.get(reverse("core:posta_messaggio", args=[email_ricevuta.pk]))

        visibili = risposta.context["allegati_visibili"]
        self.assertEqual(len(visibili), 1)
        self.assertEqual(visibili[0]["nome"], "documento.pdf")

    def test_script_e_iframe_vengono_eliminati(self):
        from apps.core.richtext import clean_email_html

        sporco = (
            '<p onclick="ruba()">Ciao</p>'
            '<script>fetch("http://male.example")</script>'
            '<iframe src="http://male.example"></iframe>'
            '<a href="javascript:alert(1)">link finto</a>'
        )
        pulito = clean_email_html(sporco)
        self.assertIn("Ciao", pulito)
        self.assertNotIn("script", pulito.lower())
        self.assertNotIn("iframe", pulito.lower())
        self.assertNotIn("onclick", pulito.lower())
        self.assertNotIn("javascript:", pulito.lower())

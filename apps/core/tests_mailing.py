"""Test mittente personalizzato e copia in Inviati via IMAP."""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from apps.core.mailing import accoda_email, archivia_in_inviati, invia_voce_coda
from apps.core.models import EmailInCoda


class FakeImap:
    """Finto server IMAP: registra l'APPEND e simula le cartelle."""

    def __init__(self, cartelle=(b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Sent"')):
        self.cartelle = cartelle
        self.append_chiamate = []

    def list(self):
        return "OK", list(self.cartelle)

    def append(self, cartella, flag, data, messaggio):
        self.append_chiamate.append((cartella, flag, messaggio))
        return "OK", []

    def logout(self):
        return "OK", []


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MittenteTest(TestCase):
    def test_mittente_aziendale_e_reply_to_personale(self):
        """Aruba rifiuta i From diversi dalla casella: si spedisce come
        azienda e l'email dell'utente diventa il Reply-To."""
        voce = accoda_email(
            to_email="cliente@example.it", subject="Ordine", message="Testo",
            descrizione="test", from_email="simone@aquaforma.it",
        )
        self.assertEqual(voce.from_email, "simone@aquaforma.it")
        invia_voce_coda(voce)
        self.assertEqual(len(mail.outbox), 1)
        from django.conf import settings

        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].extra_headers.get("Reply-To"), "simone@aquaforma.it")

    def test_senza_mittente_si_usa_quello_aziendale(self):
        from django.conf import settings

        voce = accoda_email(to_email="cliente@example.it", subject="Ordine", message="Testo")
        invia_voce_coda(voce)
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertNotIn("Reply-To", mail.outbox[0].extra_headers)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ArchiviaInviatiTest(TestCase):
    def test_copia_nella_cartella_sent(self):
        fake = FakeImap()
        with (
            mock.patch("apps.core.imap.posta_configurata", return_value=True),
            mock.patch("apps.core.imap.connetti", return_value=fake),
        ):
            self.assertTrue(archivia_in_inviati(b"Subject: test\r\n\r\ncorpo"))
        self.assertEqual(len(fake.append_chiamate), 1)
        cartella, _flag, messaggio = fake.append_chiamate[0]
        self.assertEqual(cartella, "Sent")
        self.assertIn(b"Subject: test", messaggio)

    def test_fallback_posta_inviata(self):
        fake = FakeImap(cartelle=(b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Posta inviata"'))
        with (
            mock.patch("apps.core.imap.posta_configurata", return_value=True),
            mock.patch("apps.core.imap.connetti", return_value=fake),
        ):
            self.assertTrue(archivia_in_inviati(b"test"))
        self.assertEqual(fake.append_chiamate[0][0], "Posta inviata")

    def test_cartelle_aruba_senza_virgolette(self):
        """Aruba espone le cartelle come atomi: (\\HasNoChildren \\Sent) "." INBOX.Sent."""
        fake = FakeImap(
            cartelle=(
                b'(\\HasChildren ".") "." INBOX',
                b'(\\HasNoChildren \\Sent) "." INBOX.Sent',
                b'(\\HasNoChildren \\Junk) "." INBOX.SPAM',
            )
        )
        with (
            mock.patch("apps.core.imap.posta_configurata", return_value=True),
            mock.patch("apps.core.imap.connetti", return_value=fake),
        ):
            self.assertTrue(archivia_in_inviati(b"test"))
        self.assertEqual(fake.append_chiamate[0][0], "INBOX.Sent")

    def test_senza_imap_nessun_errore(self):
        with mock.patch("apps.core.imap.posta_configurata", return_value=False):
            self.assertFalse(archivia_in_inviati(b"test"))

    def test_errore_imap_non_blocca_invio(self):
        voce = accoda_email(to_email="cliente@example.it", subject="Ordine", message="Testo")
        with (
            mock.patch("apps.core.imap.posta_configurata", return_value=True),
            mock.patch("apps.core.imap.connetti", side_effect=Exception("rete giù")),
        ):
            self.assertTrue(invia_voce_coda(voce))
        voce.refresh_from_db()
        self.assertEqual(voce.stato, EmailInCoda.STATO_INVIATA)
        self.assertEqual(len(mail.outbox), 1)

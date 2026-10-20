"""Verifiche degli strumenti MCP (scripts/mcp_read.py e scripts/mcp_write.py).

Gli strumenti servono anche fuori dall'applicazione: qui si controlla che restino
registrati e che letture e scritture seguano le regole di business. Se il
pacchetto ``mcp`` non è installato (requirements-mcp.txt, non necessario in
produzione) i test vengono saltati.
"""
import os
import sys
from pathlib import Path

from asgiref.sync import async_to_sync
from django.test import TestCase

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "scripts"))

try:
    import mcp_auth
    import mcp_http
    import mcp_read
    import mcp_write
    from mcp_common import mcp
    from starlette.testclient import TestClient

    MCP_DISPONIBILE = True
except ImportError:  # pragma: no cover - senza requirements-mcp.txt
    MCP_DISPONIBILE = False

try:
    from unittest import skipUnless
except ImportError:  # pragma: no cover
    from unittest import skipUnless


def _campioni():
    """Anagrafiche minime per i test."""
    from apps.contacts.models import Contact
    from apps.core.models import PaymentTerm, UnitOfMeasure, VatRate
    from apps.inventory.models import Warehouse

    uom, _creato = UnitOfMeasure.objects.get_or_create(code="pz", defaults={"name": "Pezzi"})
    iva, _creata = VatRate.objects.get_or_create(code="22", defaults={"name": "22%", "rate": 22})
    pagamento, _creato = PaymentTerm.objects.get_or_create(name="Fine mese", defaults={"days": 30})
    magazzino, _creato = Warehouse.objects.get_or_create(code="MAG", defaults={"name": "Magazzino"})
    cliente = Contact.objects.create(name="Cliente Test MCP", is_customer=True, payment_term=pagamento)
    return uom, iva, pagamento, magazzino, cliente


def _call(fn):
    return async_to_sync(fn)


def _prodotto(uom, iva, codice, nome, vendita=100, acquisto=60):
    from apps.catalog.models import Product

    return Product.objects.create(
        name=nome, code=codice, uom=uom, sale_vat=iva, purchase_vat=iva,
        sale_price=vendita, purchase_price=acquisto,
    )


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class RegistrazioneStrumentiTest(TestCase):
    def test_strumenti_registrati(self):
        strumenti = set(mcp._tool_manager._tools)
        self.assertGreaterEqual(len(strumenti), 85)
        for nome in [
            "cerca_clienti", "scheda_cliente", "lista_preventivi", "dettaglio_preventivo",
            "lista_ordini", "dettaglio_ordine", "ordini_da_consegnare", "lista_ddt",
            "lista_fatture", "scadenzario", "lista_ordini_fornitore", "giacenze",
            "dettaglio_articolo", "lista_commesse", "lista_lead", "crea_preventivo",
            "crea_ordine_cliente", "conferma_ordine", "crea_fattura_da_ordine",
            "registra_movimento_magazzino", "crea_cliente", "aggiorna_cliente", "crea_articolo",
            # verifica completa: letture
            "fatture_da_incassare", "voci_listino", "statistiche_vendite", "provvigioni",
            "lista_ore", "riepilogo_ore", "lista_assenze", "scheda_dipendente",
            # verifica completa: scritture
            "invia_ordine_fornitore", "conferma_ordine_fornitore", "annulla_ordine_cliente",
            "annulla_ddt", "annulla_ordine_fornitore", "crea_fattura_cantiere",
            "applica_variazione_listino", "crea_dipendente", "crea_collaboratore",
            "registra_ore", "registra_ore_collaboratore", "registra_assenza", "cambia_stato_assenza",
        ]:
            self.assertIn(nome, strumenti)

    def test_ogni_strumento_ha_descrizione_e_schema(self):
        """Descrizione e schema parametri sono quello che vede l'agente: non devono mancare."""
        for nome, strumento in mcp._tool_manager._tools.items():
            self.assertTrue((strumento.description or "").strip(), f"Il tool {nome} è senza descrizione")
            self.assertIsInstance(strumento.parameters, dict, f"Il tool {nome} è senza schema parametri")

    def test_schema_parametri(self):
        """La firma tipizzata deve arrivare allo schema che vedono gli assistenti."""
        parametri = mcp._tool_manager._tools["lista_ordini"].parameters["properties"]
        self.assertIn("stato", parametri)
        self.assertIn("da_data", parametri)
        self.assertEqual(parametri["limite"]["type"], "integer")
        self.assertEqual(parametri["offset"]["minimum"], 0)

    def test_ogni_strumento_ha_annotazioni_coerenti(self):
        """Le annotazioni MCP distinguono letture e scritture e il server resta chiuso."""
        strumenti = mcp._tool_manager._tools
        for nome, strumento in strumenti.items():
            annotazioni = strumento.annotations
            self.assertIsNotNone(annotazioni, f"Il tool {nome} è senza annotazioni")
            self.assertFalse(annotazioni.openWorldHint, f"Il tool {nome}: openWorldHint deve essere False")
        self.assertTrue(strumenti["lista_ordini"].annotations.readOnlyHint)
        self.assertFalse(strumenti["crea_preventivo"].annotations.readOnlyHint)
        self.assertFalse(strumenti["crea_preventivo"].annotations.destructiveHint)
        self.assertTrue(strumenti["annulla_ddt"].annotations.destructiveHint)

    def test_parametri_con_descrizioni_e_vincoli(self):
        """Descrizioni e vincoli dei parametri devono arrivare nello schema."""
        for nome, strumento in mcp._tool_manager._tools.items():
            for parametro in strumento.parameters.get("properties", {}).values():
                self.assertTrue(parametro.get("description"), f"Parametro senza descrizione in {nome}")
        limite = mcp._tool_manager._tools["lista_ordini"].parameters["properties"]["limite"]
        self.assertEqual((limite["minimum"], limite["maximum"]), (1, 50))
        ore = mcp._tool_manager._tools["registra_ore"].parameters["properties"]["ore"]
        self.assertEqual((ore["minimum"], ore["maximum"]), (0.25, 24))


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class LettureMcpTest(TestCase):
    def setUp(self):
        from django.utils import timezone

        from apps.sales.models import SalesOrder, SalesOrderLine

        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.prodotto = _prodotto(self.uom, self.iva, "LET001", "Vaso test MCP")
        self.ordine = SalesOrder.objects.create(
            customer=self.cliente, date=timezone.localdate(), status=SalesOrder.STATUS_CONFIRMED
        )
        SalesOrderLine.objects.create(
            order=self.ordine, position=1, product=self.prodotto, description=self.prodotto.name,
            qty=2, uom=self.uom, unit_price=100, vat_rate=self.iva,
        )
        self.ordine.recalculate()

    def test_ordini_da_consegnare(self):
        esito = _call(mcp_read.ordini_da_consegnare)()
        numeri = [o["numero"] for o in esito["ordini"]]
        self.assertIn(self.ordine.number, numeri)
        riga = esito["ordini"][0]["righe_da_consegnare"][0]
        self.assertEqual(riga["residua"], "2.000")

    def test_dettaglio_ordine(self):
        esito = _call(mcp_read.dettaglio_ordine)(self.ordine.number)
        self.assertEqual(esito["cliente"], self.cliente.name)
        self.assertEqual(esito["stato_consegna"], "Confermato")
        self.assertEqual(len(esito["righe_da_consegnare"]), 1)

    def test_numero_inesistente(self):
        esito = _call(mcp_read.dettaglio_preventivo)("INESISTENTE")
        self.assertIn("errore", esito)

    def test_stato_non_valido(self):
        esito = _call(mcp_read.lista_ordini)(stato="boh")
        self.assertIn("errore", esito)
        self.assertIn("ammessi", esito["errore"])


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class ScrittureMcpTest(TestCase):
    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.prodotto = _prodotto(self.uom, self.iva, "TST001", "Rubinetto test MCP", vendita=50, acquisto=30)

    def test_crea_preventivo_e_conversione(self):
        esito = _call(mcp_write.crea_preventivo)(
            self.cliente.name,
            righe=[{"articolo": self.prodotto.code, "quantita": 2, "prezzo": 50}],
            pagamento=self.pagamento.name,
        )
        self.assertIn("numero", esito)
        self.assertEqual(esito["totale"], "122.00")
        ordine = _call(mcp_write.converti_preventivo_in_ordine)(esito["numero"])
        self.assertEqual(ordine["da_preventivo"], esito["numero"])
        dettaglio = _call(mcp_read.dettaglio_preventivo)(esito["numero"])
        self.assertEqual(dettaglio["stato"], "Convertito in ordine")

    def test_consegna_ordine(self):
        from django.utils import timezone

        from apps.sales.models import SalesOrder, SalesOrderLine

        ordine = SalesOrder.objects.create(
            customer=self.cliente, date=timezone.localdate(), status=SalesOrder.STATUS_CONFIRMED
        )
        SalesOrderLine.objects.create(
            order=ordine, position=1, product=self.prodotto, description=self.prodotto.name,
            qty=3, uom=self.uom, unit_price=50, vat_rate=self.iva,
        )
        ordine.recalculate()
        # senza giacenza lo scarico viene rifiutato: la consegna non è registrata
        esito = _call(mcp_write.registra_consegna_ordine)(ordine.number)
        self.assertEqual(esito["stato"], "Confermato")
        self.assertTrue(esito["avvisi"])
        self.assertTrue(
            all(isinstance(a, str) and not a.startswith("['") for a in esito["avvisi"]),
            f"Gli avvisi devono essere testo pulito: {esito['avvisi']}",
        )
        # con la giacenza disponibile la consegna completa l'ordine
        _call(mcp_write.registra_movimento_magazzino)(self.prodotto.code, tipo="carico", quantita=3)
        esito = _call(mcp_write.registra_consegna_ordine)(ordine.number)
        self.assertEqual(esito["stato"], "Consegnato")
        self.assertTrue(esito["consegnato_il"])

    def test_movimento_magazzino(self):
        from decimal import Decimal

        _call(mcp_write.registra_movimento_magazzino)(self.prodotto.code, tipo="carico", quantita=5)
        giacenza = _call(mcp_read.giacenza_articolo)(self.prodotto.code)
        self.assertEqual(Decimal(giacenza["giacenza_totale"]), Decimal("5"))
        esito = _call(mcp_write.registra_movimento_magazzino)(self.prodotto.code, tipo="boh", quantita=1)
        self.assertIn("errore", esito)

    def test_righe_non_valide(self):
        esito = _call(mcp_write.crea_preventivo)(self.cliente.name, righe=[])
        self.assertIn("errore", esito)
        esito = _call(mcp_write.crea_preventivo)(
            self.cliente.name, righe=[{"articolo": "CODICE-INESISTENTE", "quantita": 1}]
        )
        self.assertIn("errore", esito)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class AggiornaClienteMcpTest(TestCase):
    """L'aggiornamento tocca solo i campi indicati e non inventa valori."""

    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.cliente.sale_discount_pct = 12
        self.cliente.save(update_fields=["sale_discount_pct"])

    def test_sconto_abituale_aggiornato(self):
        esito = _call(mcp_write.aggiorna_cliente)(self.cliente.code, sconto_vendite=5)
        self.assertNotIn("errore", esito)
        self.assertEqual(esito["sconto_vendite"], "5.00")
        self.cliente.refresh_from_db()
        self.assertEqual(str(self.cliente.sale_discount_pct), "5.00")

    def test_campi_non_indicati_restano_invariati(self):
        esito = _call(mcp_write.aggiorna_cliente)(
            self.cliente.code, citta="Milano", sconto_acquisto=8, attivo=False
        )
        self.assertNotIn("errore", esito)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.city, "Milano")
        self.assertEqual(str(self.cliente.purchase_discount_pct), "8.00")
        self.assertFalse(self.cliente.active)
        # invariati: nome e sconto vendite non sono stati passati
        self.assertEqual(self.cliente.name, "Cliente Test MCP")
        self.assertEqual(str(self.cliente.sale_discount_pct), "12.00")

    def test_pagamento_per_nome(self):
        esito = _call(mcp_write.aggiorna_cliente)(self.cliente.code, pagamento="Fine mese")
        self.assertNotIn("errore", esito)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.payment_term, self.pagamento)

    def test_errori(self):
        self.assertIn("errore", _call(mcp_write.aggiorna_cliente)(self.cliente.code))
        self.assertIn("errore", _call(mcp_write.aggiorna_cliente)("INESISTENTE", sconto_vendite=5))


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class FormatiNumericiTest(TestCase):
    """I valori numerici restano stringhe Decimal, con i decimali del campo."""

    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()

    def test_prezzo_aggiornato_conserva_i_decimali(self):
        prodotto = _prodotto(self.uom, self.iva, "FMT001", "Articolo formato", vendita=10, acquisto=5)
        esito = _call(mcp_write.aggiorna_prezzo_articolo)(prodotto.code, prezzo_vendita=15)
        self.assertNotIn("errore", esito)
        # il campo sale_price ha 4 decimali: il valore riletto dal database li mantiene
        self.assertEqual(esito["prezzo_vendita"], "15.0000")
        self.assertEqual(float(esito["prezzo_vendita"]), 15.0)
        self.assertIn("errore", _call(mcp_write.aggiorna_prezzo_articolo)(prodotto.code))

    def test_valore_decimal_senza_notazione_esponenziale(self):
        from decimal import Decimal

        from mcp_common import _valore

        self.assertEqual(_valore(Decimal("1E+2")), "100")
        self.assertEqual(_valore(Decimal("15.00")), "15.00")
        self.assertEqual(_valore(None), "")


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class ChiaviFattureTest(TestCase):
    """Le liste di fatture usano le stesse chiavi italiane dei tool di dettaglio."""

    def setUp(self):
        from django.utils import timezone

        from apps.billing.models import SalesInvoice

        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.fattura = SalesInvoice.objects.create(
            customer=self.cliente,
            date=timezone.localdate(),
            due_date=timezone.localdate(),
            status=SalesInvoice.STATUS_ISSUED,
        )
        self.fattura.lines.create(description="Riga test", qty=1, unit_price=100, vat_rate=self.iva)
        self.fattura.recalculate()

    def test_fatture_da_incassare_chiavi_italiane(self):
        esito = _call(mcp_read.fatture_da_incassare)()
        self.assertEqual(esito["totale"], 1)
        righe = esito["risultati"]
        self.assertEqual(len(righe), 1)
        for chiave in ("numero", "data", "scadenza", "cliente", "imponibile", "totale", "stato", "scaduta"):
            self.assertIn(chiave, righe[0])
        self.assertEqual(righe[0]["numero"], self.fattura.number)
        self.assertEqual(float(righe[0]["totale"]), 122.0)

    def test_scheda_cliente_fatture_aperte_chiavi_italiane(self):
        scheda = _call(mcp_read.scheda_cliente)(self.cliente.code)
        fatture = scheda["fatture_aperte"]
        self.assertEqual(len(fatture), 1)
        self.assertEqual(fatture[0]["numero"], self.fattura.number)
        for chiave in ("numero", "data", "scadenza", "stato", "totale", "scaduta"):
            self.assertIn(chiave, fatture[0])


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class StatiPreventivoTest(TestCase):
    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.prodotto = _prodotto(self.uom, self.iva, "STP001", "Articolo stati", vendita=50, acquisto=30)

    def _preventivo(self):
        esito = _call(mcp_write.crea_preventivo)(
            self.cliente.code, righe=[{"articolo": self.prodotto.code, "quantita": 1}]
        )
        self.assertNotIn("errore", esito)
        return esito["numero"]

    def test_transizioni_ammesse(self):
        numero = self._preventivo()
        self.assertNotIn("errore", _call(mcp_write.cambia_stato_preventivo)(numero, "inviato"))
        self.assertNotIn("errore", _call(mcp_write.cambia_stato_preventivo)(numero, "Accettato"))
        self.assertNotIn("errore", _call(mcp_write.cambia_stato_preventivo)(numero, "rifiutato"))

    def test_transizioni_vietate(self):
        numero = self._preventivo()
        _call(mcp_write.cambia_stato_preventivo)(numero, "rifiutato")
        esito = _call(mcp_write.cambia_stato_preventivo)(numero, "accettato")
        self.assertIn("errore", esito)

        numero2 = self._preventivo()
        _call(mcp_write.cambia_stato_preventivo)(numero2, "inviato")
        self.assertIn("errore", _call(mcp_write.cambia_stato_preventivo)(numero2, "inviato"))
        self.assertIn("errore", _call(mcp_write.cambia_stato_preventivo)(numero2, "bozza"))

    def test_convertito_non_si_ricambia(self):
        numero = self._preventivo()
        _call(mcp_write.cambia_stato_preventivo)(numero, "accettato")
        _call(mcp_write.converti_preventivo_in_ordine)(numero)
        esito = _call(mcp_write.cambia_stato_preventivo)(numero, "rifiutato")
        self.assertIn("errore", esito)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class AcquistiCompletoTest(TestCase):
    def setUp(self):
        from apps.contacts.models import Contact

        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.fornitore = Contact.objects.create(
            name="Fornitore MCP", is_supplier=True, payment_term=self.pagamento
        )
        self.prodotto = _prodotto(self.uom, self.iva, "ACQ001", "Articolo acquisti", vendita=50, acquisto=30)

    def test_flusso_completo(self):
        po = _call(mcp_write.crea_ordine_fornitore)(
            self.fornitore.code, righe=[{"articolo": self.prodotto.code, "quantita": 4}]
        )
        self.assertNotIn("errore", po)
        # appena creato è in bozza: c'è già tra quelli da ricevere (le bozze sono ricevibili)
        da_ricevere = _call(mcp_read.ordini_fornitore_da_ricevere)()
        self.assertIn(po["numero"], [o["numero"] for o in da_ricevere["ordini"]])

        inviato = _call(mcp_write.invia_ordine_fornitore)(po["numero"])
        self.assertEqual(inviato["stato"], "Inviato")
        self.assertIn("errore", _call(mcp_write.invia_ordine_fornitore)(po["numero"]))
        confermato = _call(mcp_write.conferma_ordine_fornitore)(po["numero"])
        self.assertEqual(confermato["stato"], "Confermato")
        da_ricevere = _call(mcp_read.ordini_fornitore_da_ricevere)()
        self.assertIn(po["numero"], [o["numero"] for o in da_ricevere["ordini"]])

        ricezione = _call(mcp_write.ricevi_ordine_fornitore)(po["numero"], magazzino=self.magazzino.code)
        self.assertEqual(ricezione["stato"], "Ricevuto")
        self.assertEqual(float(_call(mcp_read.giacenza_articolo)(self.prodotto.code)["giacenza_totale"]), 4.0)

        fattura = _call(mcp_write.crea_fattura_ricevuta_da_ordine_fornitore)(po["numero"])
        _call(mcp_write.registra_fattura_ricevuta)(fattura["numero"])
        _call(mcp_write.segna_fattura_ricevuta_pagata)(fattura["numero"])
        dettaglio = _call(mcp_read.dettaglio_fattura_fornitore)(fattura["numero"])
        self.assertEqual(dettaglio["stato"], "Pagata")

    def test_conferma_diretta_e_annullo(self):
        po = _call(mcp_write.crea_ordine_fornitore)(
            self.fornitore.code, righe=[{"articolo": self.prodotto.code, "quantita": 1}]
        )
        _call(mcp_write.conferma_ordine_fornitore)(po["numero"])
        annullo = _call(mcp_write.annulla_ordine_fornitore)(po["numero"])
        self.assertEqual(annullo["stato"], "Annullato")

        # un ordine già ricevuto non si annulla
        po2 = _call(mcp_write.crea_ordine_fornitore)(
            self.fornitore.code, righe=[{"articolo": self.prodotto.code, "quantita": 1}]
        )
        _call(mcp_write.ricevi_ordine_fornitore)(po2["numero"])
        esito = _call(mcp_write.annulla_ordine_fornitore)(po2["numero"])
        self.assertIn("errore", esito)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class AnnullamentiTest(TestCase):
    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.prodotto = _prodotto(self.uom, self.iva, "ANN001", "Articolo annulli", vendita=80, acquisto=50)

    def _ordine(self):
        esito = _call(mcp_write.crea_ordine_cliente)(
            self.cliente.code, righe=[{"articolo": self.prodotto.code, "quantita": 2}]
        )
        self.assertNotIn("errore", esito)
        _call(mcp_write.conferma_ordine)(esito["numero"])
        return esito["numero"]

    def test_annulla_ordine_cliente(self):
        numero = self._ordine()
        esito = _call(mcp_write.annulla_ordine_cliente)(numero)
        self.assertEqual(esito["stato"], "Annullato")
        self.assertEqual(_call(mcp_read.dettaglio_ordine)(numero)["stato"], "Annullato")

    def test_ordine_consegnato_non_si_annulla(self):
        numero = self._ordine()
        _call(mcp_write.registra_movimento_magazzino)(self.prodotto.code, tipo="carico", quantita=2)
        _call(mcp_write.registra_consegna_ordine)(numero)
        esito = _call(mcp_write.annulla_ordine_cliente)(numero)
        self.assertIn("errore", esito)

    def test_annulla_ddt_in_bozza(self):
        ordine = self._ordine()
        ddt = _call(mcp_write.crea_ddt_da_ordine)(ordine)
        esito = _call(mcp_write.annulla_ddt)(ddt["numero"])
        self.assertEqual(esito["stato"], "Annullato")

    def test_ddt_emesso_non_si_annulla(self):
        ordine = self._ordine()
        _call(mcp_write.registra_movimento_magazzino)(self.prodotto.code, tipo="carico", quantita=2)
        ddt = _call(mcp_write.crea_ddt_da_ordine)(ordine)
        _call(mcp_write.emetti_ddt)(ddt["numero"])
        esito = _call(mcp_write.annulla_ddt)(ddt["numero"])
        self.assertIn("errore", esito)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class FatturazioneCantiereTest(TestCase):
    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.prodotto = _prodotto(self.uom, self.iva, "CAN001", "Articolo cantiere", vendita=100, acquisto=60)
        self.cantiere = _call(mcp_write.crea_cantiere)(self.cliente.code, nome="Cantiere MCP")
        self.assertNotIn("errore", self.cantiere)
        ordine = _call(mcp_write.crea_ordine_cliente)(
            self.cliente.code,
            righe=[{"articolo": self.prodotto.code, "quantita": 10}],
            cantiere=self.cantiere["codice"],
        )
        self.assertNotIn("errore", ordine)
        _call(mcp_write.conferma_ordine)(ordine["numero"])

    def test_acconto_sal_saldo(self):
        codice = self.cantiere["codice"]
        acconto = _call(mcp_write.crea_fattura_cantiere)(codice, "acconto", percentuale=30)
        self.assertNotIn("errore", acconto)
        self.assertEqual(acconto["tipo"], "Acconto")
        self.assertEqual(float(acconto["totale"]), 366.0)  # 300 + IVA 22%

        sal = _call(mcp_write.crea_fattura_cantiere)(codice, "sal", percentuale=50)
        self.assertNotIn("errore", sal)
        self.assertEqual(float(sal["totale"]), 244.0)  # 200 + IVA 22%

        saldo = _call(mcp_write.crea_fattura_cantiere)(codice, "saldo")
        self.assertNotIn("errore", saldo)
        self.assertEqual(float(saldo["totale"]), 610.0)  # 500 + IVA 22%

        dettaglio = _call(mcp_read.dettaglio_commessa)(codice)
        fatturazione = dettaglio["fatturazione"]
        self.assertEqual(float(fatturazione["valore_contratto"]), 1000.0)
        self.assertEqual(float(fatturazione["residuo_da_fatturare"]), 0.0)
        self.assertEqual(fatturazione["prossimo_numero_sal"], 2)
        self.assertEqual(len(fatturazione["documenti"]), 3)

    def test_errori(self):
        codice = self.cantiere["codice"]
        self.assertIn("errore", _call(mcp_write.crea_fattura_cantiere)(codice, "boh"))
        self.assertIn("errore", _call(mcp_write.crea_fattura_cantiere)(codice, "acconto"))
        self.assertIn("errore", _call(mcp_write.crea_fattura_cantiere)(codice, "sal"))  # manca la percentuale
        # con il contratto già fatturato per intero, il saldo non ha più nulla da emettere
        _call(mcp_write.crea_fattura_cantiere)(codice, "acconto", importo=1000)
        esito = _call(mcp_write.crea_fattura_cantiere)(codice, "saldo")
        self.assertIn("errore", esito)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class PersonaleTest(TestCase):
    def setUp(self):
        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()

    def _dipendente(self):
        esito = _call(mcp_write.crea_dipendente)(
            "Mario", "Rossi", mansione="Idraulico", costo_orario=25, assunzione="01/02/2025"
        )
        self.assertNotIn("errore", esito)
        return esito

    def test_ore_e_riepilogo(self):
        dipendente = self._dipendente()
        self.assertNotIn("errore", _call(mcp_write.registra_ore)(dipendente["codice"], ore=8, descrizione="Impianto"))
        self.assertNotIn("errore", _call(mcp_write.registra_ore)(dipendente["codice"], ore=2, tipo="straordinario"))
        esito_ore = _call(mcp_read.lista_ore)(dipendente="Rossi")
        voci = esito_ore["risultati"]
        self.assertEqual(esito_ore["totale"], 2)
        self.assertEqual(len(voci), 2)
        self.assertEqual(float(voci[0]["ore"]), 2.0)  # più recente prima

        riepilogo = _call(mcp_read.riepilogo_ore)()
        self.assertEqual(float(riepilogo["totale_ore"]), 10.0)
        self.assertEqual(float(riepilogo["totale_costo"]), 250.0)
        riga = riepilogo["dipendenti"][0]
        self.assertEqual(float(riga["ordinarie"]), 8.0)
        self.assertEqual(float(riga["straordinarie"]), 2.0)

        self.assertIn("errore", _call(mcp_write.registra_ore)(dipendente["codice"], ore=0.1))
        self.assertIn("errore", _call(mcp_write.registra_ore)("Nessuno", ore=1))
        self.assertIn("errore", _call(mcp_write.registra_ore)(dipendente["codice"], ore=1, tipo="boh"))

    def test_assenze_e_saldi(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.hr.models import clamp_to_year, working_days

        dipendente = self._dipendente()
        oggi = timezone.localdate()
        dal, al = oggi, oggi + timedelta(days=1)
        assenza = _call(mcp_write.registra_assenza)(
            dipendente["codice"], tipo="ferie",
            dal=dal.strftime("%d/%m/%Y"), al=al.strftime("%d/%m/%Y"), motivo="Vacanza",
        )
        self.assertNotIn("errore", assenza)
        self.assertEqual(assenza["stato"], "Richiesta")
        elenco = _call(mcp_read.lista_assenze)(stato="richiesta")["risultati"]
        self.assertEqual(elenco[0]["id"], assenza["id"])

        approvata = _call(mcp_write.cambia_stato_assenza)(assenza["id"], "approvata")
        self.assertEqual(approvata["stato"], "Approvata")
        scheda = _call(mcp_read.scheda_dipendente)(dipendente["codice"])
        attesi = working_days(*clamp_to_year(dal, al, oggi.year))
        self.assertEqual(float(scheda["saldi"]["ferie_residue"]), 26.0 - attesi)
        self.assertEqual(scheda["ultime_assenze"][0]["stato"], "Approvata")

        self.assertIn("errore", _call(mcp_write.registra_assenza)(dipendente["codice"], tipo="ferie", dal="boh"))
        self.assertIn("errore", _call(mcp_write.registra_assenza)(dipendente["codice"], tipo="boh", dal="01/01/2026"))
        self.assertIn("errore", _call(mcp_write.cambia_stato_assenza)(assenza["id"], "boh"))
        self.assertIn("errore", _call(mcp_write.cambia_stato_assenza)(999999, "approvata"))

    def test_collaboratori(self):
        from apps.hr.models import CollaboratorTimeEntry

        collaboratore = _call(mcp_write.crea_collaboratore)(
            "Elettricista MCP", azienda="Elettro srl", specializzazione="elettricista", tariffa_oraria=30
        )
        self.assertNotIn("errore", collaboratore)
        esito = _call(mcp_write.registra_ore_collaboratore)(collaboratore["codice"], ore=5)
        self.assertNotIn("errore", esito)
        self.assertEqual(CollaboratorTimeEntry.objects.count(), 1)
        elenco = _call(mcp_read.lista_collaboratori)()["risultati"]
        self.assertTrue(any(c["codice"] == collaboratore["codice"] for c in elenco))
        self.assertIn("errore", _call(mcp_write.registra_ore_collaboratore)("Manca", ore=1))


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class StatisticheProvvigioniTest(TestCase):
    def setUp(self):
        from apps.contacts.models import Contact

        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.agente = Contact.objects.create(name="Agente MCP")
        self.prodotto = _prodotto(self.uom, self.iva, "STA001", "Articolo statistiche")

    def test_margini_e_provvigioni(self):
        ordine = _call(mcp_write.crea_ordine_cliente)(
            self.cliente.code,
            righe=[{"articolo": self.prodotto.code, "quantita": 10}],
            provvigione_a=self.agente.code,
            provvigione_pct=10,
        )
        self.assertNotIn("errore", ordine)
        _call(mcp_write.conferma_ordine)(ordine["numero"])
        _call(mcp_write.registra_movimento_magazzino)(self.prodotto.code, tipo="carico", quantita=10)
        consegna = _call(mcp_write.registra_consegna_ordine)(ordine["numero"])
        self.assertEqual(consegna["stato"], "Consegnato")

        stats = _call(mcp_read.statistiche_vendite)()
        self.assertEqual(float(stats["fatturato"]), 1000.0)
        self.assertEqual(float(stats["costo"]), 600.0)
        self.assertEqual(float(stats["provvigioni"]), 100.0)
        self.assertEqual(float(stats["margine"]), 300.0)
        self.assertEqual(stats["ordini"], 1)
        self.assertTrue(any(r["voce"] == self.cliente.name for r in stats["per_cliente"]))
        self.assertTrue(any(r["voce"] == self.prodotto.name for r in stats["per_articolo"]))
        self.assertIn("errore", _call(mcp_read.statistiche_vendite)(periodo="boh"))

        report = _call(mcp_read.provvigioni)()
        self.assertEqual(float(report["totale_provvigioni"]), 100.0)
        self.assertEqual(report["per_beneficiario"][0]["beneficiario"], self.agente.name)
        self.assertIn("errore", _call(mcp_read.provvigioni)(stato="boh"))


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class ListiniTest(TestCase):
    def setUp(self):
        from apps.contacts.models import Contact
        from apps.purchasing.models import PriceListItem, SupplierPriceList

        self.uom, self.iva, self.pagamento, self.magazzino, self.cliente = _campioni()
        self.fornitore = Contact.objects.create(name="Fornitore Listini", is_supplier=True)
        self.p1 = _prodotto(self.uom, self.iva, "LST001", "Articolo listino 1", vendita=80, acquisto=50)
        self.p2 = _prodotto(self.uom, self.iva, "LST002", "Articolo listino 2", vendita=120, acquisto=70)
        self.listino = SupplierPriceList.objects.create(name="Listino MCP", supplier=self.fornitore)
        PriceListItem.objects.create(pricelist=self.listino, product=self.p1, price=50, supplier_code="F-01")
        PriceListItem.objects.create(pricelist=self.listino, product=self.p2, price=100, discount_pct=10)

    def test_voci_e_variazione(self):
        dettaglio = _call(mcp_read.voci_listino)("Listino MCP")
        self.assertNotIn("errore", dettaglio)
        self.assertEqual(dettaglio["fornitore"], self.fornitore.name)
        voci = {v["articolo"]: v for v in dettaglio["voci"]}
        self.assertEqual(float(voci["LST001"]["prezzo"]), 50.0)
        self.assertEqual(voci["LST001"]["codice_fornitore"], "F-01")
        self.assertEqual(float(voci["LST002"]["prezzo_effettivo"]), 90.0)

        esito = _call(mcp_write.applica_variazione_listino)("Listino MCP", 10)
        self.assertNotIn("errore", esito)
        self.assertEqual(esito["voci_aggiornate"], 2)
        aggiornato = _call(mcp_read.voci_listino)("Listino MCP")
        voci = {v["articolo"]: v for v in aggiornato["voci"]}
        self.assertEqual(round(float(voci["LST001"]["prezzo"]), 2), 55.0)
        self.assertEqual(round(float(voci["LST002"]["prezzo"]), 2), 110.0)

        self.assertIn("errore", _call(mcp_write.applica_variazione_listino)("Listino MCP", 0))
        self.assertIn("errore", _call(mcp_read.voci_listino)("Non esiste"))

    def test_nome_ambiguo(self):
        from apps.purchasing.models import SupplierPriceList

        SupplierPriceList.objects.create(name="Listino MCP bis", supplier=self.fornitore)
        # nome esatto: risolve comunque
        esatto = _call(mcp_read.voci_listino)("Listino MCP")
        self.assertEqual(esatto["listino"], "Listino MCP")
        # parte del nome comune a due listini: serve più precisione
        esito = _call(mcp_read.voci_listino)("Listino MC")
        self.assertIn("errore", esito)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class PaginazioneTest(TestCase):
    """Gli elenchi riportano i metadati di paginazione e si possono scorrere con offset."""

    def setUp(self):
        from apps.contacts.models import Contact

        for indice in range(3):
            Contact.objects.create(name=f"Cliente Pagina {indice}", is_customer=True)

    def test_scorrimento_elenco(self):
        prima = _call(mcp_read.cerca_clienti)("Cliente Pagina", limite=2)
        self.assertEqual(prima["totale"], 3)
        self.assertEqual(prima["offset"], 0)
        self.assertTrue(prima["has_more"])
        self.assertEqual(prima["prossimo_offset"], 2)
        self.assertEqual(len(prima["risultati"]), 2)

        seconda = _call(mcp_read.cerca_clienti)("Cliente Pagina", limite=2, offset=2)
        self.assertEqual(len(seconda["risultati"]), 1)
        self.assertFalse(seconda["has_more"])
        self.assertIsNone(seconda["prossimo_offset"])

    def test_ricerca_troppo_corta(self):
        esito = _call(mcp_read.cerca_clienti)("X")
        self.assertIn("errore", esito)

    def test_bucket_con_metadati(self):
        esito = _call(mcp_read.preventivi_in_scadenza)(limite=1)
        for bucket in ("preventivi_scaduti", "preventivi_in_scadenza"):
            self.assertIn("totale", esito[bucket])
            self.assertIn("has_more", esito[bucket])
            self.assertIn("prossimo_offset", esito[bucket])


# ========================================================== autenticazione
@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class AutenticazioneMcpTest(TestCase):
    """Il token decide chi entra e a chi sono attribuite le scritture."""

    def setUp(self):
        from django.test import override_settings

        self.ambiente = override_settings()
        self.ambiente.enable()
        self.addCleanup(self.ambiente.disable)
        self.salvato = {
            chiave: os.environ.get(chiave)
            for chiave in (
                "MCP_TOKEN",
                "MCP_TOKENS",
                "MCP_USER",
                "MCP_ALLOWED_IPS",
                "MCP_RATE_LIMIT",
                "MCP_ALLOWED_HOSTS",
                "MCP_ALLOWED_ORIGINS",
            )
        }
        for chiave in self.salvato:
            os.environ.pop(chiave, None)
        # L'host del client di test: è l'unico ammesso.
        os.environ["MCP_ALLOWED_HOSTS"] = "testserver"
        self.addCleanup(self._ripristina_ambiente)

    def _ripristina_ambiente(self):
        for chiave, valore in self.salvato.items():
            if valore is None:
                os.environ.pop(chiave, None)
            else:
                os.environ[chiave] = valore

    def test_token_valido_riconosciuto(self):
        os.environ["MCP_TOKEN"] = "segreto-123"
        os.environ["MCP_USER"] = "admin"
        self.assertTrue(mcp_auth.token_valido("segreto-123"))
        self.assertFalse(mcp_auth.token_valido("segreto-124"))
        self.assertFalse(mcp_auth.token_valido(""))

    def test_token_per_utente(self):
        os.environ["MCP_TOKENS"] = "aaa:marco,bbb:giulia"
        credenziale = mcp_auth.verifica_token("bbb")
        self.assertIsNotNone(credenziale)
        self.assertEqual(credenziale.username, "giulia")
        self.assertFalse(credenziale.sola_lettura)

    def test_scope_sola_lettura(self):
        os.environ["MCP_TOKENS"] = "aaa:marco:mcp:sola-lettura"
        credenziale = mcp_auth.verifica_token("aaa")
        self.assertIsNotNone(credenziale)
        self.assertTrue(credenziale.sola_lettura)

    def test_allowlist_ip(self):
        os.environ["MCP_ALLOWED_IPS"] = "10.0.0.1,10.0.0.2"
        self.assertTrue(mcp_auth.ip_consentito("10.0.0.1"))
        self.assertFalse(mcp_auth.ip_consentito("10.0.0.9"))
        self.assertFalse(mcp_auth.ip_consentito(None))

    def test_allowlist_vuota_ammette_tutti(self):
        self.assertTrue(mcp_auth.ip_consentito("1.2.3.4"))

    def test_rate_limit(self):
        limitatore = mcp_auth.Limitatore(limite=2)
        self.assertTrue(limitatore.ammesso("marco"))
        self.assertTrue(limitatore.ammesso("marco"))
        self.assertFalse(limitatore.ammesso("marco"))
        # un altro utente ha un proprio conteggio
        self.assertTrue(limitatore.ammesso("giulia"))

    def test_rate_limit_disattivato(self):
        limitatore = mcp_auth.Limitatore(limite=0)
        for _ in range(50):
            self.assertTrue(limitatore.ammesso("marco"))

    def test_middleware_rifiuta_senza_token(self):
        os.environ["MCP_TOKEN"] = "segreto-123"
        os.environ["MCP_USER"] = "admin"
        app = mcp_http.applicazione_http()
        with TestClient(app, base_url="http://testserver") as client:
            risposta = client.post("/mcp", json=_richiesta_inizializzazione())
            self.assertEqual(risposta.status_code, 401)

    def test_middleware_rifiuta_token_sbagliato(self):
        os.environ["MCP_TOKEN"] = "segreto-123"
        os.environ["MCP_USER"] = "admin"
        app = mcp_http.applicazione_http()
        with TestClient(app, base_url="http://testserver") as client:
            risposta = client.post(
                "/mcp",
                json=_richiesta_inizializzazione(),
                headers={"Authorization": "Bearer sbagliato"},
            )
            self.assertEqual(risposta.status_code, 401)

    def test_middleware_accetta_token_valido(self):
        os.environ["MCP_TOKEN"] = "segreto-123"
        os.environ["MCP_USER"] = "admin"
        app = mcp_http.applicazione_http()
        with TestClient(app, base_url="http://testserver") as client:
            risposta = client.post(
                "/mcp",
                json=_richiesta_inizializzazione(),
                headers=_intestazioni("segreto-123"),
            )
            self.assertEqual(risposta.status_code, 200)
            self.assertIn("gestionale", risposta.text)

    def test_server_http_rifiuta_senza_credenziali(self):
        with self.assertRaises(RuntimeError):
            mcp_http.applicazione_http()

    def test_host_non_ammesso_rifiutato(self):
        os.environ["MCP_TOKEN"] = "segreto-123"
        os.environ["MCP_USER"] = "admin"
        app = mcp_http.applicazione_http()
        with TestClient(app, base_url="http://altro.example") as client:
            risposta = client.post(
                "/mcp",
                json=_richiesta_inizializzazione(),
                headers={"Authorization": "Bearer segreto-123"},
            )
            self.assertEqual(risposta.status_code, 421)


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class AttribuzioneUtenteMcpTest(TestCase):
    """Le scritture degli assistenti AI restano attribuite a una persona."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.utente = get_user_model().objects.create_user(username="mcp-utente", password="segreto12345")
        self._uom, self._iva, _pagamento, _magazzino, self.cliente = _campioni()

    def _con_credenziale(self, credenziale):
        """Restituisce un contesto che impersona l'utente del token."""
        from contextlib import contextmanager

        from mcp_auth import credenziale_attuale

        @contextmanager
        def contesto():
            segnaposto = credenziale_attuale.set(credenziale)
            try:
                yield
            finally:
                credenziale_attuale.reset(segnaposto)

        return contesto()

    def test_ordine_attribuito_all_utente(self):
        from apps.sales.models import SalesOrder

        credenziale = mcp_auth.Credenziale(token="t", username=self.utente.username)
        with self._con_credenziale(credenziale):
            esito = _call(mcp_write.crea_ordine_cliente)(
                cliente=self.cliente.name,
                righe=[{"tipo": "articolo", "descrizione": "Riga di prova", "quantita": 1}],
            )
        self.assertIn("messaggio", esito)
        ordine = SalesOrder.objects.order_by("-pk").first()
        self.assertEqual(ordine.created_by, self.utente)

    def test_registro_attivita_con_utente(self):
        from apps.core.models import ActivityLog

        credenziale = mcp_auth.Credenziale(token="t", username=self.utente.username)
        with self._con_credenziale(credenziale):
            _call(mcp_write.crea_preventivo)(
                cliente=self.cliente.name,
                righe=[{"tipo": "articolo", "descrizione": "Riga di prova", "quantita": 1}],
            )
        righe = ActivityLog.objects.filter(model_name="Preventivo")
        self.assertTrue(righe.exists())
        self.assertTrue(all(riga.user == self.utente for riga in righe))

    def test_token_sola_lettura_non_scrive(self):
        credenziale = mcp_auth.Credenziale(
            token="t", username=self.utente.username, scope=mcp_auth.SCOPE_SOLA_LETTURA
        )
        with self._con_credenziale(credenziale):
            esito = _call(mcp_write.crea_preventivo)(
                cliente=self.cliente.name,
                righe=[{"tipo": "articolo", "descrizione": "Riga di prova", "quantita": 1}],
            )
        self.assertIn("errore", esito)
        from apps.sales.models import Quote

        self.assertFalse(Quote.objects.exists())


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class ErroriPrevistiTest(TestCase):
    """Gli errori frequenti tornano come messaggio, non come stack trace."""

    def test_valori_non_finiti_rifiutati(self):
        from mcp_common import _dec

        for testo in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                _dec(testo)

    def test_valori_validi_accettati(self):
        from decimal import Decimal

        from mcp_common import _dec

        self.assertEqual(_dec("15,50"), Decimal("15.50"))
        self.assertEqual(_dec(""), Decimal("0"))

    def test_errori_del_database_gestiti(self):
        from django.db import DataError, IntegrityError

        from mcp_common import _sicuro

        def alza(exc):
            def funzione():
                raise exc

            return funzione

        for exc in (IntegrityError("UNIQUE"), DataError("too long")):
            esito = _sicuro(alza(exc))
            self.assertIn("errore", esito)

    def test_errori_imprevisti_restano_eccezioni(self):
        from mcp_common import _sicuro

        def funzione():
            raise RuntimeError("bug vero")

        with self.assertRaises(RuntimeError):
            _sicuro(funzione)

    def test_log_audit_registra_la_chiamata(self):
        from mcp_common import _registra_chiamata

        with self.assertLogs("apps.mcp", level="INFO") as registri:
            _registra_chiamata(_funzione_di_prova, 0.0, "ok")
        self.assertTrue(any("MCP" in riga for riga in registri.output))


def _funzione_di_prova():
    """Funzione fittizia per il log di audit."""
    return None


def _richiesta_inizializzazione() -> dict:
    """Messaggio JSON-RPC di inizializzazione del protocollo MCP."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }


def _intestazioni(token: str | None = None) -> dict:
    """Intestazioni di una richiesta MCP (token facoltativo)."""
    intestazioni = {"Accept": "application/json, text/event-stream"}
    if token:
        intestazioni["Authorization"] = f"Bearer {token}"
    return intestazioni


@skipUnless(MCP_DISPONIBILE, "pacchetto mcp non installato (requirements-mcp.txt)")
class EspansioneKitMcpTest(TestCase):
    """Un kit inserito da un assistente AI viene espanso come nell'interfaccia."""

    def test_preventivo_con_kit_espanso(self):
        from apps.catalog.models import KitComponent
        from apps.sales.models import Quote

        uom, iva, _pagamento, _magazzino, cliente = _campioni()
        componente = _prodotto(uom, iva, "KIT-COMP-1", "Componente del kit")
        kit = _prodotto(uom, iva, "KIT-1", "Kit completo")
        kit.is_kit = True
        kit.is_stock_tracked = False
        kit.save()
        KitComponent.objects.create(kit=kit, component=componente, qty=2)

        esito = _call(mcp_write.crea_preventivo)(
            cliente=cliente.name,
            righe=[{"tipo": "articolo", "articolo": "KIT-1", "quantita": 1}],
        )
        self.assertIn("messaggio", esito)
        preventivo = Quote.objects.order_by("-pk").first()
        righe = list(preventivo.lines.all())
        self.assertEqual(len(righe), 2)
        self.assertTrue(any("componente" in riga.description.lower() for riga in righe))
        # il totale non cambia: i componenti sono a prezzo zero
        self.assertEqual(preventivo.subtotal, kit.sale_price)

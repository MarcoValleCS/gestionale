"""Importazione dei listini dei fornitori.

Ogni produttore manda il listino in un formato diverso: qui c'è un lettore per
ciascuno. Il comando crea o aggiorna articoli, varianti, categorie e voci di
listino, così i prezzi restano modificabili dal gestionale.

Uso:
    python manage.py importa_listini colavene --file "…\\listino Colavene.xlsx"
    python manage.py importa_listini axa --file "…\\AXA_Listino.xlsx"
    python manage.py importa_listini lacus --file "…\\listino 2026 barcode.xls"
    python manage.py importa_listini duplach --file "…\\Listino Prezzi DUPLACH.xlsx"
    python manage.py importa_listini forma-aquae --file "…\\LISTINO ITALIA.xlsx"

Opzioni utili:
    --dry-run       mostra cosa verrebbe creato senza scrivere nulla
    --ricarico 50   imposta il prezzo di vendita = listino + 50%
    --scorta 2      scorta minima per il riordino automatico (predefinita 1)
    --solo-nuovi    non aggiorna gli articoli già presenti
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

# ------------------------------------------------------------------ pulizia nomi

# Parole che restano maiuscole: unità di misura, sigle, formati
SIGLE = {
    "CM", "MM", "ML", "MQ", "MC", "PZ", "KG", "LT", "NR", "GR", "H", "SX", "DX",
    "RAL", "LED", "ABS", "PVC", "XL", "XXL", "WC", "PMMA", "MDF", "HPL", "BT", "QI",
}

# Abbreviazioni ricorrenti nei listini (chiave → testo esteso)
ABBREVIAZIONI = {
    "C/RIPIANO": "CON RIPIANO",
    "C/RIP": "CON RIPIANO",
    "S/F.R.": "SENZA FORO",
    "C/FORO": "CON FORO",
    "S/FORO": "SENZA FORO",
    "C/2": "CON 2",
    "C/1": "CON 1",
    "C/3": "CON 3",
    "C/": "CON ",
    "S/": "SENZA ",
    "P/": "PER ",
    "C/ATTACCO": "CON ATTACCO",
    "LAV.": "LAVABO",
    "LAVAP.": "LAVAPIATTI",
    "SOSP.": "SOSPESO",
    "SOSP/APP": "SOSPESO/APPOGGIO",
    "APP.": "APPOGGIO",
    "STRUTT.": "STRUTTURA",
    "STRUTT": "STRUTTURA",
    "STRUT.": "STRUTTURA",
    "STRUT": "STRUTTURA",
    "COL.": "COLONNA",
    "QUADR.": "QUADRATA",
    "QUADR": "QUADRATA",
    "RIP.": "RIPIANO",
    "NICH.": "NICHELATA",
    "NIC.": "NICHELATA",
    "CERN.": "CERNIERA",
    "SCOLAP.": "SCOLAPIATTI",
    "AVV.": "AVVITABILE",
    "APPEND.": "APPENDIABITI",
    "ZINC.": "ZINCATO",
    "CROM.": "CROMATO",
    "P.DOCCIA": "PIATTO DOCCIA",
    "P.DOCCE": "PIATTI DOCCIA",
    "P.BATTENTE": "PORTA BATTENTE",
    "P.SCORREVOLE": "PORTA SCORREVOLE",
    "P.SCORR": "PORTA SCORREVOLE",
    "P.SCOR": "PORTA SCORREVOLE",
    "P.BATT": "PORTA BATTENTE",
    "P.D": "PIATTO DOCCIA",
    "SCORR.": "SCORREVOLE",
    "SCORR": "SCORREVOLE",
    "BATT.": "BATTENTE",
    "O.SPACE": "OPEN SPACE",
    "B.CO": "BIANCO",
    "B. LUC.": "BIANCO LUCIDO",
    "B. LUC": "BIANCO LUCIDO",
    "BCO": "BIANCO",
    "MOL.": "MOLLA",
    "NORM.": "NORMALE",
    "CER.": "CERNIERA",
    "VERS.": "VERSIONE",
    "CASS.": "CASSETTO",
    "CAS.": "CASSETTO",
    "INT.": "INTERNO",
    "EST.": "ESTERNO",
    "REVERS.": "REVERSIBILE",
    "PORTAS.": "PORTASAPONE",
    "DISP.": "DISPENSER",
    "ILL.": "ILLUMINATO",
    "ATT.": "ATTACCO",
    "SUPP.": "SUPPORTO",
    "SUPP": "SUPPORTO",
    "NORM.": "NORMALE",
    "NORM": "NORMALE",
    "APPEND.": "APPENDIABITI",
    "APPEND": "APPENDIABITI",
    "ZINC.": "ZINCATO",
    "ZINC": "ZINCATO",
    "NICH.": "NICHELATA",
    "NICH": "NICHELATA",
    "NIC.": "NICHELATA",
    "NIC": "NICHELATA",
    "CROM.": "CROMATO",
    "CROM": "CROMATO",
    "CASS.": "CASSETTO",
    "CASS": "CASSETTO",
    "BR.": "BRACCIO",
    "PIEGHEV.": "PIEGHEVOLE",
    "PIEGHEV": "PIEGHEVOLE",
    "G.ROS": "GOLD ROSE",
    "CM.": "CM",
    "X": "PER",
}

# Colori e finiture: se attaccati alla parola precedente si separano
FINITURE = [
    "VISONE", "ROVERE", "PINO", "PIOMBO", "NERO", "BIANCO", "TALCO", "SPAZZOLATO",
    "BRONZO", "COR-TEN", "GRAFICA", "RAME", "ARGENTO", "NATURALE", "CEMENTO",
    "SAHARA", "NOCCIOLA", "PETROLIO", "TRAMONTO", "LAGO", "TERRA", "ARDESIA",
    "CIOCCOLATO", "MOKA", "SABBIA", "ANTRACITE", "CREMA", "CROMO", "NICKEL",
    "GOLD", "BLACK", "STEEL", "WENGÉ", "WENGE", "NOCE", "MOGANO", "LARICE",
    "BIANCO TALCO", "ROVERE NATURALE",
]

# Nomi di linea/collezione: spesso attaccati alla parola precedente
LINEE = [
    "ALAQUA", "CAMALEO", "VOLANT", "SKYLAND", "SMARTOP", "TINO", "MADIA", "BRAVA",
    "COLF", "CENTO", "JOLLY WASH", "JOLLYWASH", "TWIST", "LINDO", "DUO", "SWASH",
    "CLAUDIA", "CUCINA FACILE", "PROGETTO SMART", "PROGETTO", "ACQUACERAMICA",
    "ACTIVE WASH", "JOLLY", "PALMARIA", "ALBARELLA", "SPACE", "EVO", "CLOUD",
    "ANTA",
]


def normalizza_spazi(testo):
    testo = str(testo or "")
    # residui dei file Excel: ritorni a capo codificati come testo
    testo = testo.replace("_x000D_", " ").replace("_x000d_", " ")
    testo = testo.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    # caratteri di controllo e asterischi di evidenziazione dei listini
    testo = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", testo)
    testo = re.sub(r"^\s*[\*\-–]+\s*", "", testo)
    testo = re.sub(r"\s+", " ", testo)
    # refusi ricorrenti nei listini
    testo = re.sub(r"\bma\s+tt\b", "matt", testo, flags=re.I)
    testo = re.sub(r"\s+([,.;:])", r"\1", testo)
    return testo.strip(" ;-–,")


def espandi_abbreviazioni(testo):
    """Sostituisce le sigle dei listini in un'unica passata.

    In una sola passata le sostituzioni non si applicano l'una all'altra
    (altrimenti «STRUTT.» diventerebbe «STRUTTURA URA»).
    """
    chiavi = sorted(ABBREVIAZIONI, key=len, reverse=True)
    alternativa = "|".join(re.escape(chiave) for chiave in chiavi)
    # Sigla attaccata alla parola successiva: solo per le sigle con il punto
    # (CERN.PIANA → CERNIERA PIANA). Le sigle senza punto si applicano solo
    # isolate, altrimenti «CROM» spezzerebbe «CROMO».
    con_punto = sorted([chiave for chiave in chiavi if chiave.endswith(".")], key=len, reverse=True)
    if con_punto:
        alternativa_punto = "|".join(re.escape(chiave) for chiave in con_punto)
        testo = re.sub(
            rf"(?<![A-Za-z0-9])({alternativa_punto})(?=[A-Za-z0-9])",
            lambda trovato: f"{ABBREVIAZIONI[trovato.group(1).upper()]} ",
            testo,
            flags=re.IGNORECASE,
        )
    # Sigla isolata: NIC. → NICHELATA
    testo = re.sub(
        rf"(?<![A-Za-z0-9])({alternativa})(?![A-Za-z0-9])",
        lambda trovato: ABBREVIAZIONI[trovato.group(1).upper()],
        testo,
        flags=re.IGNORECASE,
    )
    return testo


def separa_finiture(testo):
    """Separa colori, finiture e nomi di linea attaccati alla parola precedente."""
    for parola in sorted(FINITURE + LINEE, key=len, reverse=True):
        testo = re.sub(rf"(?<=[A-Za-z0-9])({re.escape(parola)})\b", r" \1", testo)
        # attaccato a una misura: TWIST60X50 → TWIST 60X50
        testo = re.sub(rf"(?<=[A-Za-z/])({re.escape(parola)})(?=[0-9])", r"\1 ", testo)
    return testo


def titola(testo):
    """Prima lettera maiuscola, sigle e misure in maiuscolo."""
    parole = []
    for parola in testo.split():
        pulita = parola.strip(".,;:")
        if not pulita:
            continue
        if pulita.upper() in SIGLE:
            parole.append(parola.upper())
            continue
        if re.fullmatch(r"[0-9][0-9xX×*.,/\-°]*[a-zA-Z]?", parola) or re.fullmatch(r"[A-Za-z]?[0-9][0-9xX×*.,/\-°]*", parola):
            parole.append(parola.upper())
            continue
        pezzi = re.split(r"([\-/])", parola)
        ricomposta = []
        for pezzo in pezzi:
            if pezzo in {"-", "/"}:
                ricomposta.append(pezzo)
            elif pezzo:
                ricomposta.append(pezzo[:1].upper() + pezzo[1:].lower())
        parole.append("".join(ricomposta))
    return " ".join(parole)


def pulisci_nome(descrizione, esteso=False):
    """Rende leggibile una descrizione di listino."""
    testo = normalizza_spazi(descrizione)
    testo = separa_finiture(testo)
    testo = espandi_abbreviazioni(testo)
    testo = normalizza_spazi(testo)
    testo = titola(testo)
    return normalizza_spazi(testo)


def numero(valore):
    """Converte un valore di cella in numero decimale (0 se non valido)."""
    if valore is None or valore == "":
        return Decimal("0")
    if isinstance(valore, (int, float)):
        return Decimal(str(valore))
    testo = str(valore).strip().replace("€", "").replace(" ", "")
    if "," in testo and "." in testo:
        testo = testo.replace(".", "").replace(",", ".")
    else:
        testo = testo.replace(",", ".")
    try:
        return Decimal(testo)
    except (InvalidOperation, ValueError):
        return Decimal("0")


# ------------------------------------------------------------------ lettori


@dataclass
class Voce:
    codice: str
    nome: str
    prezzo: Decimal
    unita: str = "PZ"
    barcode: str = ""
    gruppo: str = ""
    descrizione: str = ""
    variante_di: str = ""          # codice dell'articolo principale (esiste già)
    famiglia: str = ""             # nome della famiglia da creare (piatti doccia)
    etichetta_variante: str = ""
    note: str = ""


def leggi_colavene(percorso):
    """Colavene (listino generale): gruppo, codice, descrizione, prezzo, unità, barcode."""
    import openpyxl

    libro = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
    foglio = libro["LISTINO 5-26"] if "LISTINO 5-26" in libro.sheetnames else libro.worksheets[0]
    for riga in foglio.iter_rows(min_row=4, values_only=True):
        codice = normalizza_spazi(riga[1])
        descrizione = normalizza_spazi(riga[2])
        if not codice or not descrizione:
            continue
        yield Voce(
            codice=codice,
            nome=pulisci_nome(descrizione),
            prezzo=numero(riga[3]),
            unita=normalizza_spazi(riga[4]).upper() or "PZ",
            barcode=normalizza_spazi(riga[5]),
            gruppo=normalizza_spazi(riga[0]),
            note=normalizza_spazi(riga[6]),
        )
    libro.close()


def leggi_axa(percorso):
    """AXA / Alchimie (Colavene): collezione, codice, descrizione, EAN, prezzo."""
    import openpyxl

    libro = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
    foglio = libro["AXA_listino_pricelist"] if "AXA_listino_pricelist" in libro.sheetnames else libro.worksheets[0]
    for riga in foglio.iter_rows(min_row=6, values_only=True):
        codice = normalizza_spazi(riga[1])
        descrizione = normalizza_spazi(riga[2])
        if not codice or not descrizione:
            continue
        yield Voce(
            codice=codice,
            nome=pulisci_nome(descrizione),
            prezzo=numero(riga[4]),
            barcode=normalizza_spazi(riga[3]),
            gruppo=normalizza_spazi(riga[0]),
            note=normalizza_spazi(riga[5]),
        )
    libro.close()


def leggi_lacus(percorso):
    """Lacus: descrizione italiana lunga (colonna 6) e codice a barre."""
    import xlrd

    libro = xlrd.open_workbook(percorso)
    foglio = libro.sheet_by_name("ARTICOLI") if "ARTICOLI" in libro.sheet_names() else libro.sheet_by_index(0)
    for indice in range(1, foglio.nrows):
        codice = normalizza_spazi(foglio.cell_value(indice, 1))
        if not codice:
            continue
        breve = normalizza_spazi(foglio.cell_value(indice, 2))
        italiana = normalizza_spazi(foglio.cell_value(indice, 5))
        # «70x120h3p.d» → «70x120 h3 p.d»: misure e sigle attaccate
        breve = re.sub(r"(?<=[0-9])(h|cm|mm|p|l)(?=[0-9a-z]|\b)", r" \1", breve, flags=re.I)
        # Il nome è la descrizione breve del listino (quella italiana è spesso la
        # finitura o il materiale: va nella descrizione estesa).
        nome = breve or italiana
        gruppo = normalizza_spazi(foglio.cell_value(indice, 0))
        yield Voce(
            codice=codice,
            nome=pulisci_nome(nome),
            prezzo=numero(foglio.cell_value(indice, 3)),
            barcode=normalizza_spazi(foglio.cell_value(indice, 4)),
            gruppo="Componenti box doccia" if gruppo.upper() == "COMPONENTE" else "Box doccia",
            descrizione=pulisci_nome(italiana) if italiana and italiana != nome else "",
        )


def leggi_duplach(percorso):
    """Duplach: piatti doccia per collezione, con colore e finitura (varianti)."""
    import openpyxl

    libro = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
    for foglio in libro.worksheets:
        # la riga 2 contiene le intestazioni: serve a trovare le colonne del prezzo
        intestazioni = []
        for riga in foglio.iter_rows(min_row=2, max_row=2, values_only=True):
            intestazioni = [normalizza_spazi(v).upper() for v in riga]
            break
        prezzi = [i for i, testo in enumerate(intestazioni) if "PREZZO" in testo]
        if not prezzi:
            continue
        # le fasce sono affiancate ogni 8 colonne (0, 8, 16…)
        blocchi = [((colonna_prezzo // 8) * 8, colonna_prezzo) for colonna_prezzo in prezzi]

        for riga in foglio.iter_rows(min_row=4, values_only=True):
            for partenza, colonna_prezzo in blocchi:
                if colonna_prezzo >= len(riga):
                    continue
                codice = normalizza_spazi(riga[partenza])
                descrizione = normalizza_spazi(riga[partenza + 1])
                if not codice or not descrizione or len(codice) < 5:
                    continue
                prezzo = numero(riga[colonna_prezzo])
                misure = [normalizza_spazi(riga[partenza + 2]), normalizza_spazi(riga[partenza + 3])]
                # 070 → 70: le misure restano leggibili
                misure = [m.lstrip("0") or m for m in misure if m]
                colore = normalizza_spazi(riga[partenza + 4])
                finitura = normalizza_spazi(riga[partenza + 5])
                verso = ""
                if colonna_prezzo - partenza > 6:
                    verso = normalizza_spazi(riga[colonna_prezzo - 1])
                nome_base = pulisci_nome(descrizione)
                if misure:
                    nome_base = f"{nome_base} {'x'.join(misure)}"
                etichetta = " ".join([p for p in (colore, finitura) if p]).title()
                if verso:
                    etichetta = f"{etichetta} {verso}".strip()
                yield Voce(
                    codice=codice,
                    nome=nome_base,
                    prezzo=prezzo,
                    barcode="",
                    gruppo=f"Duplach {foglio.title.split(' ')[0]}",
                    famiglia=nome_base,
                    etichetta_variante=etichetta,
                    note=normalizza_spazi(riga[partenza + 1]),
                )
    libro.close()


def leggi_forma_aquae(percorso):
    """Forma Aquae: codice, descrizione, prezzo; le versioni COL/TOTCOL diventano varianti."""
    import openpyxl

    libro = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
    foglio = libro.worksheets[0]
    voci = []
    for riga in foglio.iter_rows(min_row=2, values_only=True):
        codice = normalizza_spazi(riga[0])
        descrizione = normalizza_spazi(riga[1])
        if not codice or not descrizione or "PREZZO" in descrizione.upper():
            continue
        voci.append((codice, descrizione, numero(riga[2])))

    codici = {codice for codice, _, _ in voci}
    for codice, descrizione, prezzo in voci:
        base = re.sub(r"(TOTCOL|COL)$", "", codice)
        etichetta = ""
        if base != codice and base in codici:
            etichetta = "Total Color" if codice.endswith("TOTCOL") else "Color System"
        nome = pulisci_nome(descrizione)
        nome = re.sub(r"\bColor System\b", "", nome, flags=re.I)
        nome = re.sub(r"\bTotal Color\b", "", nome, flags=re.I)
        nome = normalizza_spazi(nome)
        yield Voce(
            codice=codice,
            nome=nome,
            prezzo=prezzo,
            gruppo="Lavabi e vasche",
            variante_di=base if etichetta else "",
            etichetta_variante=etichetta,
        )
    libro.close()


LETTORI = {
    "colavene": (leggi_colavene, "Colavene srl", "Listino generale Colavene"),
    "axa": (leggi_axa, "Colavene srl", "AXA / Alchimie"),
    "lacus": (leggi_lacus, "Lacus srl", "Listino 2026"),
    "duplach": (leggi_duplach, "Duplach", "Listino prezzi"),
    "forma-aquae": (leggi_forma_aquae, "Forma Aquae", "Listino Italia 2025"),
}


class Command(BaseCommand):
    help = "Importa un listino fornitore (articoli, varianti, prezzi) da file Excel."

    def add_arguments(self, parser):
        parser.add_argument("fornitore", choices=sorted(LETTORI), help="Quale listino importare.")
        parser.add_argument("--file", required=True, help="Percorso del file del listino.")
        parser.add_argument("--nome-listino", default="", help="Nome da dare al listino nel gestionale.")
        parser.add_argument("--scorta", type=float, default=1, help="Scorta minima per il riordino automatico (0 per non impostarla).")
        parser.add_argument("--ricarico", type=float, default=0, help="Ricarico %% sul prezzo di vendita (0 = da definire).")
        parser.add_argument("--solo-nuovi", action="store_true", help="Non aggiorna gli articoli già presenti.")
        parser.add_argument("--dry-run", action="store_true", help="Mostra il risultato senza salvare.")

    def handle(self, *args, **options):
        chiave = options["fornitore"]
        lettore, fornitore_predefinito, listino_predefinito = LETTORI[chiave]
        percorso = Path(options["file"])
        if not percorso.is_file():
            raise CommandError(f"File non trovato: {percorso}")

        nome_listino = options["nome_listino"] or listino_predefinito
        voci = list(lettore(percorso))
        self.stdout.write(f"  listino «{nome_listino}» di {fornitore_predefinito}: {len(voci)} voci lette")

        if options["dry_run"]:
            self.stdout.write("\n  (prova senza salvare) prime 12 voci:")
            for voce in voci[:12]:
                extra = f" · variante «{voce.etichetta_variante}» di «{voce.variante_di}»" if voce.variante_di else ""
                self.stdout.write(f"    {voce.codice:<20} {voce.nome[:62]:<64} {voce.prezzo:>10} €{extra}")
            return

        from apps.catalog.models import Category, Product
        from apps.contacts.models import Contact
        from apps.core.models import UnitOfMeasure, VatRate
        from apps.purchasing.models import PriceListItem, SupplierPriceList

        iva = VatRate.objects.filter(code="22").first() or VatRate.objects.first()
        unita_default = UnitOfMeasure.objects.filter(code="PZ").first() or UnitOfMeasure.objects.first()
        unita_per_codice = {u.code.upper(): u for u in UnitOfMeasure.objects.all()}
        scorta = Decimal(str(options["scorta"]))
        ricarico = Decimal(str(options["ricarico"])) / Decimal("100")
        solo_nuovi = options["solo_nuovi"]

        fornitore, _ = Contact.objects.get_or_create(
            name=fornitore_predefinito,
            defaults={"is_supplier": True, "active": True, "notes": f"Fornitore importato dai listini ({chiave})."},
        )
        if not fornitore.is_supplier:
            fornitore.is_supplier = True
            fornitore.save(update_fields=["is_supplier"])

        categoria_padre, _ = Category.objects.get_or_create(name=fornitore_predefinito)
        listino, _ = SupplierPriceList.objects.get_or_create(
            supplier=fornitore,
            name=nome_listino,
            defaults={"notes": f"Importato da {percorso.name}."},
        )

        # il capofamiglia delle varianti può essere già stato creato (Forma Aquae):
        # qui si tiene traccia di quelli letti, per non ricercarli ogni volta
        prodotti_per_nome = {}

        creati = aggiornati = varianti = voci_listino = 0
        codici_usati = {}
        with transaction.atomic():
            for voce in voci:
                unita = unita_per_codice.get(voce.unita.upper(), unita_default)
                categoria = None
                if voce.gruppo:
                    nome_categoria = pulisci_nome(voce.gruppo)[:100]
                    # se la categoria esiste già (anche creata da altri listini) si usa
                    # quella: i nomi delle categorie sono unici
                    categoria = Category.objects.filter(name=nome_categoria).first()
                    if categoria is None:
                        categoria = Category.objects.create(name=nome_categoria, parent=categoria_padre)

                chiave_codice = voce.codice.upper()
                occorrenza = codici_usati.get(chiave_codice, 0) + 1
                codici_usati[chiave_codice] = occorrenza
                if occorrenza > 1:
                    # Codice ripetuto nello stesso listino: sono due articoli
                    # diversi (capita nei file dei fornitori). Il codice interno
                    # resta lo stesso a ogni reimportazione, così non si creano
                    # doppioni.
                    codice_interno = f"{voce.codice}-{occorrenza}"[:40]
                    esistente = Product.objects.filter(code=codice_interno).first()
                    codice_forzato = codice_interno
                else:
                    esistente = Product.objects.filter(code=voce.codice).first() if voce.codice else None
                    codice_forzato = voce.codice
                if esistente is not None and esistente.main_supplier_id not in (None, fornitore.pk):
                    # codice già usato da un altro fornitore: si crea un articolo
                    # nuovo, il codice del fornitore resta nella voce di listino
                    esistente = None

                if esistente is not None:
                    prodotto = esistente
                    codice_prodotto = esistente.code
                else:
                    prodotto = None
                    codice_prodotto = codice_forzato
                    # se il codice è libero si usa quello del fornitore,
                    # altrimenti il gestionale ne assegna uno interno
                    if codice_prodotto and Product.objects.filter(code=codice_prodotto).exists():
                        codice_prodotto = ""

                genitore = None
                if voce.variante_di:
                    genitore = Product.objects.filter(code=voce.variante_di).first()
                elif voce.famiglia:
                    genitore = prodotti_per_nome.get(voce.famiglia)
                    if genitore is None:
                        genitore = Product.objects.filter(
                            name__iexact=voce.famiglia[:200], main_supplier=fornitore
                        ).first()
                        if genitore is None:
                            # il capofamiglia non è un pezzo fisico: fa da contenitore
                            # delle varianti (colore/finitura), ognuna con il suo codice
                            genitore = Product.objects.create(
                                name=voce.famiglia[:200],
                                category=categoria,
                                uom=unita,
                                sale_vat=iva,
                                purchase_vat=iva,
                                main_supplier=fornitore,
                                is_stock_tracked=False,
                                min_stock=Decimal("0"),
                                active=True,
                            )
                            creati += 1
                        prodotti_per_nome[voce.famiglia] = genitore

                nome_finale = voce.nome
                if genitore is not None and voce.etichetta_variante:
                    nome_finale = f"{genitore.name} – {voce.etichetta_variante}"[:200]

                if prodotto is None:
                    prodotto = Product(
                        code=codice_prodotto,
                        name=nome_finale[:200],
                        description=voce.descrizione[:2000],
                        category=categoria,
                        uom=unita,
                        barcode=voce.barcode[:50],
                        sale_price=(voce.prezzo * (1 + ricarico)).quantize(Decimal("0.0001")) if ricarico else Decimal("0"),
                        sale_vat=iva,
                        purchase_price=voce.prezzo,
                        purchase_vat=iva,
                        main_supplier=fornitore,
                        is_stock_tracked=True,
                        min_stock=scorta,
                        parent=genitore,
                        variant_label=voce.etichetta_variante[:60],
                        active=True,
                    )
                    prodotto.save()
                    creati += 1
                    if genitore is not None:
                        varianti += 1
                else:
                    campi = {}
                    if not solo_nuovi:
                        if nome_finale and nome_finale != prodotto.name:
                            campi["name"] = nome_finale[:200]
                        if voce.prezzo and voce.prezzo != prodotto.purchase_price:
                            campi["purchase_price"] = voce.prezzo
                        if voce.barcode and not prodotto.barcode:
                            campi["barcode"] = voce.barcode[:50]
                        if categoria and prodotto.category_id != categoria.pk:
                            campi["category"] = categoria
                        if not prodotto.is_stock_tracked:
                            campi["is_stock_tracked"] = True
                        if scorta and not prodotto.min_stock:
                            campi["min_stock"] = scorta
                        if prodotto.main_supplier_id is None:
                            campi["main_supplier"] = fornitore
                    if campi:
                        for campo, valore in campi.items():
                            setattr(prodotto, campo, valore)
                        prodotto.save(update_fields=list(campi))
                        aggiornati += 1

                if genitore is None and voce.variante_di:
                    # è il capofamiglia delle varianti: si ricorda per le righe dopo
                    prodotti_per_nome[voce.variante_di] = prodotto

                PriceListItem.objects.update_or_create(
                    pricelist=listino,
                    product=prodotto,
                    defaults={
                        "supplier_code": voce.codice[:60],
                        "price": voce.prezzo,
                        "note": voce.note[:200],
                    },
                )
                voci_listino += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  articoli creati: {creati} · aggiornati: {aggiornati} · varianti: {varianti} · voci di listino: {voci_listino}"
            )
        )

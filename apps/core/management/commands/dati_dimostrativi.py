"""Popola il gestionale con dati dimostrativi realistici.

Serve a far provare il gestionale a chi non lo conosce: clienti, fornitori,
articoli con giacenze, listini, cantieri, preventivi in ogni stato, ordini
cliente e fornitore, DDT, fatture, provvigioni, movimenti di magazzino,
personale, collaboratori con le loro ore e foto di cantiere.

Uso:
    python manage.py dati_dimostrativi            # aggiunge i dati mancanti
    python manage.py dati_dimostrativi --reset    # azzera e ricrea tutto

Con ``--reset`` vengono cancellati solo i dati "di lavoro": utenti, gruppi e
dati azienda restano intatti.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.billing import services as billing_services
from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice
from apps.catalog.models import Category, Product
from apps.contacts.models import Contact
from apps.core.models import Attachment, CompanySettings, PaymentTerm, Tag, UnitOfMeasure, VatRate
from apps.hr.models import Collaborator, CollaboratorTimeEntry, Employee, LeaveRequest, TimeEntry
from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement
from apps.jobs.models import Job, MaintenancePlan
from apps.purchasing.models import PriceListItem, PurchaseOrder, PurchaseOrderLine, SupplierPriceList
from apps.sales import services as sales_services
from apps.sales.models import Quote, QuoteLine, QuoteTemplate, QuoteTemplateLine, SalesOrder, SalesOrderLine

ZERO = Decimal("0")
PASSWORD_DEMO = "Demo2026!"

# --------------------------------------------------------------- clienti
CLIENTI = [
    ("Marco Rossi", "Via Giuseppe Verdi 12", "24050", "Zanica", "BG", "335 1234567", "marco.rossi@example.it"),
    ("Laura Bianchi", "Via San Bernardino 4", "24122", "Bergamo", "BG", "340 2233445", "laura.bianchi@example.it"),
    ("Andrea Colombo", "Via Monte Grappa 21", "24047", "Treviglio", "BG", "347 9988776", "andrea.colombo@example.it"),
    ("Famiglia Ferrari", "Via Vittorio Emanuele 8", "24020", "Scanzorosciate", "BG", "338 5566778", "ferrari.famiglia@example.it"),
    ("Giulia Moretti", "Via Garibaldi 33", "24121", "Bergamo", "BG", "333 4455667", "giulia.moretti@example.it"),
    ("Stefano Riva", "Via Kennedy 5", "24044", "Dalmine", "BG", "328 1122334", "stefano.riva@example.it"),
    ("Hotel Villa Serena srl", "Via dei Mille 40", "24100", "Bergamo", "BG", "035 123456", "info@villaserena.example.it"),
    ("Studio Architettura Bertoni", "Via Tasso 15", "24121", "Bergamo", "BG", "035 654321", "studio@bertoni.example.it"),
    ("Impresa Edile Fratelli Locatelli snc", "Via Artigiani 7", "24030", "Presezzo", "BG", "035 987654", "info@locatelli.example.it"),
    ("Condominio Le Vele", "Via Autostrada 62", "24126", "Bergamo", "BG", "035 445566", "amministrazione@levele.example.it"),
    ("Rifugio La Baita snc", "Località Pizzo 1", "24016", "San Pellegrino Terme", "BG", "0345 22334", "info@labaita.example.it"),
    ("Dental Center Dr. Parisi", "Via Borgo Palazzo 88", "24125", "Bergamo", "BG", "035 778899", "segreteria@dentalparisi.example.it"),
    ("Beauty & Spa Aurora srl", "Via Pignolo 120", "24121", "Bergamo", "BG", "035 334455", "info@spaaurora.example.it"),
    ("Centro Sportivo Orobico", "Via Palazzolo 210", "24050", "Orio al Serio", "BG", "035 556677", "segreteria@orobico.example.it"),
    ("Agriturismo Cascina Nova", "Via Campagna 3", "24020", "Torre de' Roveri", "BG", "035 667788", "info@cascinanova.example.it"),
    ("B&B Il Giardino Segreto", "Via Ripa 9", "24123", "Bergamo", "BG", "345 7788990", "info@giardinosegreto.example.it"),
    ("Amministrazione Palazzo Aurora", "Via Angelo Maj 18", "24121", "Bergamo", "BG", "035 221133", "palazzo.aurora@example.it"),
    ("Tenuta Sant'Ambrogio", "Via Sant'Ambrogio 25", "24040", "Bolgare", "BG", "035 889900", "info@tenutasambrogio.example.it"),
]

# --------------------------------------------------------------- fornitori
FORNITORI = [
    ("Hansgrohe srl", "Via Milano 12", "20093", "Cologno Monzese", "MI", "02251601", "ordini@hansgrohe.example.it"),
    ("Lacus srl", "Via dell'Industria 30", "25030", "Castegnato", "BS", "030 123456", "info@lacus.example.it"),
    ("Azzurra Sanitari in Ceramica spa", "Via Cavour 15", "25030", "Grumello del Monte", "BG", "035 446677", "ordini@azzurra.example.it"),
    ("Colavene srl", "Via Petrarca 8", "46019", "Viadana", "MN", "0375 890123", "vendite@colavene.example.it"),
    ("We Do Home srl", "Via delle Industrie 5", "36040", "Brendola", "VI", "0444 789012", "info@wedohome.example.it"),
    ("Cordivari srl", "Via Paganica 8", "64100", "Teramo", "TE", "0861 234567", "info@cordivari.example.it"),
    ("Almar srl", "Via Aldo Moro 44", "06083", "Bastia Umbra", "PG", "075 890567", "ordini@almarwellness.example.it"),
    ("Daniel Rubinetterie spa", "Via Dante 1", "25020", "Flero", "BS", "030 35801", "info@danielrubinetterie.example.it"),
    ("Novellini spa", "Via Mantova 28", "46036", "Revere", "MN", "0386 62611", "info@novellini.example.it"),
    ("A.F.I.S. G. Clerici spa", "Via Marconi 30", "20010", "Boffalora sopra Ticino", "MI", "02 9723111", "ordini@afis.it"),
    ("Ferramenta Bergamasca snc", "Via Autostrada 5", "24126", "Bergamo", "BG", "035 332211", "info@ferramentabg.example.it"),
    ("Geda srl", "Via dell'Artigianato 2", "24060", "Castelli Calepio", "BG", "035 442233", "ordini@geda.example.it"),
]

# ------------------------------------------------------ agenti provvigioni
AGENTI = [
    ("Rappresentanze Bergamo snc", "Via Borgo Santa Caterina 12", "24124", "Bergamo", "BG", "035 556644"),
    ("Agente Marco Vitali", "Via San Tomaso 8", "24121", "Bergamo", "BG", "333 9988776"),
    ("Agenzia Idrocommerciale nord", "Via Milano 130", "24040", "Stezzano", "BG", "035 998811"),
]

# ---------------------------------------------------------------- articoli
# (codice, descrizione, categoria, prezzo vendita, costo, fornitore, scorta minima, giacenza)
ARTICOLI = [
    # sanitari
    ("0201801", "GLOMP wc sospeso scarico A-SOUND - bianco lucido", "Sanitari", "315.00", "196.00", "Azzurra Sanitari in Ceramica spa", "2", "6"),
    ("0202001", "GLOMP bidet sospeso - bianco lucido", "Sanitari", "294.00", "183.00", "Azzurra Sanitari in Ceramica spa", "2", "5"),
    ("339101", "FLAT sedile soft closing sgancio rapido - bianco lucido", "Sanitari", "91.00", "53.00", "Azzurra Sanitari in Ceramica spa", "4", "12"),
    ("8801401", "EVA vaso a terra norim - bianco lucido", "Sanitari", "292.00", "170.00", "Azzurra Sanitari in Ceramica spa", "2", "4"),
    ("8802201", "EVA bidet a terra - bianco lucido", "Sanitari", "292.00", "170.00", "Azzurra Sanitari in Ceramica spa", "2", "3"),
    ("AF8801", "EVA coprivaso slim chiusura soft - bianco", "Sanitari", "130.00", "76.00", "A.F.I.S. G. Clerici spa", "3", "8"),
    ("AF0015", "piletta s&g c/clip in ceramica - bianco", "Sanitari", "44.00", "24.00", "A.F.I.S. G. Clerici spa", "10", "35"),
    ("FI010", "fissaggio orizzontale x vaso/bidet", "Accessori bagno", "6.00", "3.10", "A.F.I.S. G. Clerici spa", "20", "60"),
    ("540388", "sifone lavabo salvaspazio x mobile", "Scarichi e sifoni", "10.00", "5.20", "Colavene srl", "15", "48"),
    ("AF0004", "curva tecnica 10/15", "Scarichi e sifoni", "33.00", "18.00", "A.F.I.S. G. Clerici spa", "6", "18"),
    ("AF0016", "raccordo eccentrico 1,5 cm per ingresso", "Scarichi e sifoni", "22.00", "12.00", "A.F.I.S. G. Clerici spa", "6", "14"),
    # rubinetteria
    ("JAG91D1", "JAGO mix lavabo mf c/piletta clic-clack - cromo", "Rubinetteria", "165.00", "96.00", "Lacus srl", "3", "9"),
    ("JAG94D1", "JAGO mix bidet mf c/piletta clic-clack - cromo", "Rubinetteria", "192.00", "112.00", "Lacus srl", "3", "7"),
    ("JAG451", "JAGO p.est. mix incasso 2 vie rotativo - cromo", "Rubinetteria", "96.00", "56.00", "Lacus srl", "4", "11"),
    ("IST45", "parte incasso x mix 2 vie devio rotativo", "Rubinetteria", "215.00", "124.00", "Lacus srl", "3", "6"),
    ("E214015.CO316", "STILL mix lavabo mf s/scarico - pvd copper br.", "Rubinetteria", "389.00", "238.00", "We Do Home srl", "1", "3"),
    ("E214024.CO316", "STILL mix bidet mf s/scarico - pvd copper br.", "Rubinetteria", "442.00", "271.00", "We Do Home srl", "1", "2"),
    ("E180142.CO", "MODULAR p.est. mix 2 vie c/duplex - piastre singole", "Rubinetteria", "616.00", "378.00", "We Do Home srl", "1", "2"),
    ("BE022AA", "CERALIFE O p. est mix incasso 1 via - cromo", "Rubinetteria", "85.00", "52.00", "Lacus srl", "4", "10"),
    ("BE021AA", "CERALIFE O mix bidet mf c/piletta u&d - cromo", "Rubinetteria", "113.00", "66.00", "Lacus srl", "3", "8"),
    ("BE100AA", "CERALIFE O mix lavabo mf c/pil. u&d - cromo", "Rubinetteria", "155.00", "96.00", "Lacus srl", "3", "6"),
    ("24161000", "Pulsify select s - set doccia 105 3jet relax ecosmart", "Rubinetteria", "128.00", "71.00", "Hansgrohe srl", "3", "7"),
    ("37859000", "SURF placca di comando Grohe - cromo", "Rubinetteria", "89.00", "56.00", "Hansgrohe srl", "3", "4"),
    # doccia
    ("E021112.CR", "braccio doccia tondo l=350 - ottone - cromo", "Doccia", "112.00", "66.00", "We Do Home srl", "3", "8"),
    ("E044298.CR", "VELVET soffione 23x23 - ispezionabile", "Doccia", "235.00", "142.00", "We Do Home srl", "2", "5"),
    ("E095039.CR", "presa acqua c/supp. piastra quadra - cromo", "Doccia", "88.00", "50.00", "We Do Home srl", "3", "9"),
    ("E082130.CR", "doccino cilindro abs cromo", "Doccia", "31.00", "17.00", "We Do Home srl", "6", "16"),
    ("C084021.CR", "flessibile pvc flex l=1500 - cromo", "Doccia", "23.00", "12.50", "We Do Home srl", "8", "22"),
    ("WBOX612D2", "WBOX incasso 2 vie verticale", "Doccia", "62.00", "36.00", "We Do Home srl", "3", "7"),
    ("DPL.13090", "piatto doccia 130x90 - texture ardesia", "Piatti doccia", "448.00", "284.00", "Novellini spa", "1", "3"),
    ("DPL.17090", "piatto doccia 170x90 - texture ardesia", "Piatti doccia", "523.00", "332.00", "Novellini spa", "1", "2"),
    ("DPL.COLOR", "supplemento colore RAL/NCS", "Piatti doccia", "60.00", "0", "Novellini spa", "0", "0"),
    ("KUADH120-1H", "KUADRA parete fissa 117/120 nero opaco", "Box doccia", "910.00", "578.00", "Novellini spa", "1", "2"),
    ("DEB.100.70", "box doccia scorrevole 100x70 h=190 cristallo 6mm", "Box doccia", "640.00", "402.00", "Novellini spa", "1", "3"),
    ("DEB.140.80", "box doccia scorrevole 140x80 h=190 cristallo 6mm", "Box doccia", "740.00", "468.00", "Novellini spa", "1", "2"),
    ("VRF4.072.30.TR", "VERA lato fisso 72/74 6mm h200 - argento lucido", "Box doccia", "486.00", "308.00", "Novellini spa", "1", "2"),
    # mobili e specchi
    ("CS1040904840", "JEY base 2 cassetti l=90 h=50 p=46,6 c/pianolavabo", "Mobili bagno", "912.00", "578.00", "We Do Home srl", "1", "4"),
    ("B12C50705", "JEY base lavabo 2 cass. l=700 p=500 h=500", "Mobili bagno", "644.00", "408.00", "We Do Home srl", "1", "3"),
    ("C01AG0353", "colonna 1anta l=35 p=36 h=160 finitura dekor", "Mobili bagno", "340.00", "215.00", "We Do Home srl", "1", "2"),
    ("BALDO", "specchio 2 tondi sovrapp. c/led diffusion - l=120 h=80", "Specchi e luci", "272.00", "172.00", "We Do Home srl", "1", "3"),
    ("CAPSULA.60120", "specchio l=60 h=120 c/led diffusion 4300K", "Specchi e luci", "308.00", "195.00", "We Do Home srl", "1", "2"),
    ("BOREAL", "faretto led tondo 4300K", "Specchi e luci", "30.00", "15.00", "We Do Home srl", "6", "14"),
    ("KAYRA.90.80", "specchio l=90 h=80 filo lucido retro illuminato", "Specchi e luci", "243.00", "154.00", "We Do Home srl", "1", "2"),
    ("THEMIS.105.70", "specchio l=105 h=70", "Specchi e luci", "425.00", "269.00", "We Do Home srl", "1", "2"),
    # scaldasalviette
    ("351356100238.R01", "CLAUDIA scaldasalviette elettrico l=500 h=1100", "Scaldasalviette", "498.00", "315.00", "Cordivari srl", "1", "2"),
    ("3551626102064", "SAMIRA scaldasalviette l=40 h=100 - cromo", "Scaldasalviette", "642.00", "406.00", "Cordivari srl", "1", "2"),
    ("351356100238.SPECIAL", "CLAUDIA scaldasalviette elettrico su misura", "Scaldasalviette", "685.00", "433.00", "Cordivari srl", "0", "1"),
    # accessori
    ("WQO13.08", "EQUILIBRIUM pta accappatoio cromo", "Accessori bagno", "94.00", "56.00", "Almar srl", "3", "7"),
    ("EQO06/11DX.08", "EQUILIBRIUM pta salviette + rotolo verso dx", "Accessori bagno", "116.00", "70.00", "Almar srl", "3", "6"),
    ("1946.08", "EQUILIBRIUM mini pta scopino sospeso cromo", "Accessori bagno", "85.00", "51.00", "Almar srl", "3", "5"),
    ("E310002.CO", "appendiabito singolo pvd copper br.", "Accessori bagno", "81.00", "48.00", "We Do Home srl", "4", "9"),
    ("37059000", "Grohtherm miscelatore termostatico doccia", "Rubinetteria", "268.00", "160.00", "Hansgrohe srl", "2", "4"),
    # piscine
    ("PMP.SPEED400", "pompa di ricircolo autoadescante 400 W", "Piscine", "289.00", "178.00", "Geda srl", "1", "3"),
    ("FILT.SAND500", "filtro a sabbia d.500 c/valvola 6 vie", "Piscine", "395.00", "246.00", "Geda srl", "1", "2"),
    ("CLORO.MULTI5", "cloro multiazione 5 kg", "Piscine", "48.00", "27.00", "Geda srl", "6", "18"),
    ("ROBOT.2WD", "robot pulizia fondo piscina 2 ruote", "Piscine", "780.00", "512.00", "Geda srl", "1", "2"),
    ("SCALA.3GR", "scala piscina 3 gradini inox", "Piscine", "310.00", "196.00", "Geda srl", "1", "3"),
    ("TELO.INV", "telo invernale su misura al mq", "Piscine", "22.00", "11.00", "Geda srl", "0", "0"),
    ("BOMBOLA.PH", "correttore pH liquido 5 lt", "Piscine", "26.00", "13.00", "Geda srl", "6", "15"),
    # servizi (non a magazzino)
    ("POSA.IDR", "posa in opera idraulica (ora)", "Servizi", "48.00", "0", "", "0", "0"),
    ("POSA.PIAST", "posa piastrelle e rivestimenti (ora)", "Servizi", "42.00", "0", "", "0", "0"),
    ("MONTAGGIO", "montaggio mobili e sanitari (ora)", "Servizi", "45.00", "0", "", "0", "0"),
    ("TRASPORTO", "trasporto e consegna in cantiere", "Servizi", "60.00", "0", "", "0", "0"),
    ("SMALTIMENTO", "smaltimento imballaggi e materiali", "Servizi", "90.00", "0", "", "0", "0"),
    ("APERTURA.PISC", "apertura piscina stagionale", "Servizi", "350.00", "0", "", "0", "0"),
    ("CHIUSURA.PISC", "chiusura piscina e invernaggio", "Servizi", "320.00", "0", "", "0", "0"),
    ("PROGETTO", "progettazione e rilievo in cantiere", "Servizi", "180.00", "0", "", "0", "0"),
]

# ---------------------------------------------------------------- cantieri
CANTIERI = [
    ("Ristrutturazione bagno Via Verdi", "Via Giuseppe Verdi 12", "24050", "Zanica", "BG", Job.STATUS_CLOSED, "Marco Rossi"),
    ("Bagno Hotel Villa Serena - camere 1-3 piano", "Via dei Mille 40", "24100", "Bergamo", "BG", Job.STATUS_IN_PROGRESS, "Hotel Villa Serena srl"),
    ("Villa privata con piscina - Scanzorosciate", "Via Vittorio Emanuele 8", "24020", "Scanzorosciate", "BG", Job.STATUS_IN_PROGRESS, "Famiglia Ferrari"),
    ("Complesso residenziale Le Vele - 6 bagni", "Via Autostrada 62", "24126", "Bergamo", "BG", Job.STATUS_QUOTE, "Condominio Le Vele"),
    ("Bagno di servizio uffici Locatelli", "Via Artigiani 7", "24030", "Presezzo", "BG", Job.STATUS_SURVEY, "Impresa Edile Fratelli Locatelli snc"),
    ("Manutenzione piscina Centro Sportivo Orobico", "Via Palazzolo 210", "24050", "Orio al Serio", "BG", Job.STATUS_IN_PROGRESS, "Centro Sportivo Orobico"),
    ("Bagno Beauty & Spa Aurora", "Via Pignolo 120", "24121", "Bergamo", "BG", Job.STATUS_TESTING, "Beauty & Spa Aurora srl"),
    ("Rifacimento bagni B&B Il Giardino Segreto", "Via Ripa 9", "24123", "Bergamo", "BG", Job.STATUS_CLOSED, "B&B Il Giardino Segreto"),
]


class Command(BaseCommand):
    help = "Crea dati dimostrativi realistici per far provare il gestionale."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Cancella i dati di lavoro prima di ricrearli")
        parser.add_argument("--senza-foto", action="store_true", help="Non generare le foto di cantiere")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.casuale = random.Random(20261002)
        self.articoli = {}
        self.clienti = {}
        self.fornitori = {}
        self.cantieri = {}
        self.utenti_demo = []

    # ------------------------------------------------------------------ main
    def handle(self, *args, **options):
        from apps.core.activity import registro_sospeso

        self.rif = self._riferimenti()
        with registro_sospeso():
            if options["reset"]:
                self._svuota()
            with transaction.atomic():
                self._azienda()
                self._utenti()
                self._contatti()
                self._articoli()
                self._listini()
                self._cantieri()
                self._preventivi()
                self._ordini_cliente()
                self._ordini_fornitore()
                self._ddt()
                self._provvigioni_del_mese()
                self._fatture()
                self._manutenzioni()
                self._personale()
                self._collaboratori()
                if not options["senza_foto"]:
                    self._foto()
        self._riepilogo()

    # ----------------------------------------------------------- riferimenti
    def _riferimenti(self):
        vat22 = VatRate.objects.filter(code="22", is_active=True).first()
        vat10 = VatRate.objects.filter(code="10", is_active=True).first()
        vat4 = VatRate.objects.filter(code="4", is_active=True).first()
        pz = UnitOfMeasure.objects.get(code="PZ")
        ore = UnitOfMeasure.objects.filter(code="H").first() or UnitOfMeasure.objects.create(code="H", name="Ora")
        mq = UnitOfMeasure.objects.filter(code="MQ").first() or UnitOfMeasure.objects.create(code="MQ", name="Metro quadro")

        pagamenti = {}
        for nome, giorni, fine_mese in (
            ("Rimessa diretta", 0, False),
            ("Bonifico 30 giorni", 30, False),
            ("Bonifico 60 giorni", 60, False),
            ("Bonifico 30 gg fine mese", 30, True),
        ):
            pagamenti[nome], _ = PaymentTerm.objects.get_or_create(
                name=nome, defaults={"days": giorni, "end_of_month": fine_mese}
            )

        tags = {}
        for nome, colore in (
            ("VIP", "primary"),
            ("Nuovo cliente", "info"),
            ("Cantiere grosso", "warning"),
            ("Piscine", "success"),
            ("Arredo bagno", "secondary"),
        ):
            tags[nome], _ = Tag.objects.get_or_create(name=nome, defaults={"color": colore})

        return {"vat22": vat22, "vat10": vat10, "vat4": vat4, "pz": pz, "ore": ore, "mq": mq,
                "pagamenti": pagamenti, "tags": tags}

    # -------------------------------------------------------------- svuotamento
    def _svuota(self):
        """Cancella i dati di lavoro: utenti, gruppi e dati azienda restano."""
        self.stdout.write("  Svuoto i dati esistenti (utenti e dati azienda restano)...")
        for modello in (DeliveryNote, SalesInvoice, PurchaseInvoice, SalesOrder, Quote):
            modello.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        PriceListItem.objects.all().delete()
        SupplierPriceList.objects.all().delete()
        StockMovement.objects.all().delete()
        QuoteTemplate.objects.all().delete()
        MaintenancePlan.objects.all().delete()
        Job.objects.all().delete()
        Attachment.objects.all().delete()
        CollaboratorTimeEntry.objects.all().delete()
        Collaborator.objects.all().delete()
        TimeEntry.objects.all().delete()
        LeaveRequest.objects.all().delete()
        Employee.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Contact.objects.all().delete()

    # ----------------------------------------------------------------- azienda
    def _azienda(self):
        azienda = CompanySettings.load()
        azienda.name = azienda.name if azienda.name and azienda.name != "La mia azienda" else "Aquaforma srl"
        azienda.theme_color = "#0f766e"
        azienda.document_color = "#0f766e"
        azienda.document_style = "moderno"
        azienda.theme_background = "soft"
        azienda.fiscal_regime = azienda.fiscal_regime or "RF01"
        azienda.country = azienda.country or "Italia"
        if not azienda.quote_footer:
            azienda.quote_footer = (
                "Pagamento: come concordato.\n"
                "Prezzi IVA esclusa salvo diversa indicazione.\n"
                "Consegna e posa da concordare in base alla disponibilità dei materiali."
            )
        # logo per i documenti stampati, preso dal file del progetto
        if not azienda.logo:
            from django.conf import settings as dj_settings

            percorso = dj_settings.BASE_DIR / "static" / "brand" / "aquaforma-logo-scuro.png"
            if percorso.exists():
                with open(percorso, "rb") as file_logo:
                    azienda.logo.save("aquaforma-logo.png", ContentFile(file_logo.read()), save=False)
        azienda.save()

    # ------------------------------------------------------------------ utenti
    def _utenti(self):
        """Utenti demo, uno per ruolo, per far provare le diverse sezioni."""
        utenti = [
            ("demo.vendite", "Elena Vendite", "Vendite"),
            ("demo.acquisti", "Paolo Acquisti", "Acquisti"),
            ("demo.magazzino", "Giuseppe Magazzino", "Magazzino"),
            ("demo.ufficio", "Chiara Ufficio", "Personale"),
            ("demo.collaboratore", "Mario Scavi", "Collaboratore"),
        ]
        for username, nome, gruppo in utenti:
            utente, creato = get_user_model().objects.get_or_create(
                username=username,
                defaults={"first_name": nome.split()[0], "last_name": nome.split()[-1], "is_staff": True},
            )
            utente.set_password(PASSWORD_DEMO)
            utente.is_staff = True
            utente.save()
            gruppo_obj = Group.objects.filter(name=gruppo).first()
            if gruppo_obj:
                utente.groups.set([gruppo_obj])
            self.utenti_demo.append((username, gruppo, "creato" if creato else "aggiornato"))

    # --------------------------------------------------------------- contatti
    def _contatti(self):
        vat = self.rif["vat22"]
        for indice, (nome, via, cap, citta, prov, telefono, email) in enumerate(CLIENTI):
            cliente = Contact.objects.create(
                name=nome,
                is_customer=True,
                is_supplier=False,
                vat_number=f"{10000000000 + indice * 137:011d}" if "srl" in nome or "snc" in nome or "spa" in nome else "",
                tax_code="" if "srl" in nome or "snc" in nome else f"RSSMRC{70 + indice:02d}A123{(indice % 26) + 65}",
                email=email,
                phone=telefono,
                mobile=telefono if telefono.startswith("3") else "",
                address=via,
                zip_code=cap,
                city=citta,
                province=prov,
                payment_term=self.rif["pagamenti"]["Bonifico 30 giorni"],
                sale_discount_pct=Decimal(self.casuale.choice(["0", "0", "0", "5", "8", "10"])),
                notes="" if indice % 3 else "Cliente storico: segue manutenzione piscina stagionale.",
            )
            cliente.tags.add(self.rif["tags"]["Arredo bagno"])
            if indice < 3:
                cliente.tags.add(self.rif["tags"]["VIP"])
            self.clienti[nome] = cliente

        for indice, (nome, via, cap, citta, prov, telefono, email) in enumerate(FORNITORI):
            fornitore = Contact.objects.create(
                name=nome,
                is_customer=False,
                is_supplier=True,
                vat_number=f"{20000000000 + indice * 251:011d}",
                email=email,
                phone=telefono,
                address=via,
                zip_code=cap,
                city=citta,
                province=prov,
                payment_term=self.rif["pagamenti"]["Bonifico 60 giorni"],
                notes="Fornitore abituale.",
            )
            self.fornitori[nome] = fornitore

        for nome, via, cap, citta, prov, telefono in AGENTI:
            agente = Contact.objects.create(
                name=nome,
                is_customer=False,
                is_supplier=True,
                email=f"{nome.lower().replace(' ', '.')[:20]}@example.it",
                phone=telefono,
                address=via,
                zip_code=cap,
                city=citta,
                province=prov,
                notes="Agente: provvigione sulle vendite presentate.",
            )
            self.clienti[nome] = agente

        self.stdout.write(f"  Contatti: {len(self.clienti)} clienti e {len(self.fornitori)} fornitori")

    # --------------------------------------------------------------- articoli
    def _articoli(self):
        categorie = {}
        for nome in {riga[2] for riga in ARTICOLI}:
            categorie[nome], _ = Category.objects.get_or_create(name=nome, defaults={"notes": f"Articoli: {nome.lower()}"})

        for codice, descrizione, categoria, prezzo, costo, fornitore, scorta, giacenza in ARTICOLI:
            servizio = categoria == "Servizi"
            articolo = Product.objects.create(
                code=codice,
                name=descrizione,
                category=categorie[categoria],
                uom=self.rif["ore"] if servizio else self.rif["pz"],
                sale_price=Decimal(prezzo),
                sale_vat=self.rif["vat22"],
                purchase_price=Decimal(costo),
                purchase_vat=self.rif["vat22"],
                main_supplier=self.fornitori.get(fornitore),
                min_stock=Decimal(scorta),
                is_stock_tracked=not servizio,
                description=f"{categoria} · {descrizione}",
            )
            self.articoli[codice] = articolo
            quantita = Decimal(giacenza)
            if quantita > 0 and not servizio:
                register_movement(
                    product=articolo,
                    delta=quantita,
                    movement_type=StockMovement.TYPE_LOAD,
                    note="Carico iniziale di magazzino",
                    unit_cost=Decimal(costo) if costo != "0" else None,
                )

        self.stdout.write(f"  Articoli: {len(self.articoli)} in {len(categorie)} categorie, giacenze caricate")

    # ---------------------------------------------------------------- listini
    def _listini(self):
        listini = {
            "Hansgrohe srl": [("24161000", "71.00"), ("37859000", "56.00"), ("37059000", "160.00")],
            "Lacus srl": [("JAG91D1", "96.00"), ("JAG94D1", "112.00"), ("JAG451", "56.00"), ("BE022AA", "52.00")],
            "Azzurra Sanitari in Ceramica spa": [("0201801", "196.00"), ("0202001", "183.00"), ("339101", "53.00")],
            "Novellini spa": [("DPL.13090", "284.00"), ("KUADH120-1H", "578.00"), ("DEB.100.70", "402.00")],
            "We Do Home srl": [("E214015.CO316", "238.00"), ("BALDO", "172.00"), ("CAPSULA.60120", "195.00")],
        }
        righe = 0
        for nome_fornitore, voci in listini.items():
            fornitore = self.fornitori.get(nome_fornitore)
            if not fornitore:
                continue
            listino, _ = SupplierPriceList.objects.get_or_create(
                supplier=fornitore,
                name=f"Listino {timezone.localdate().year}",
                defaults={"notes": "Listino fornitori con sconti di categoria."},
            )
            for codice, prezzo in voci:
                articolo = self.articoli.get(codice)
                if articolo is None:
                    continue
                PriceListItem.objects.create(pricelist=listino, product=articolo, price=Decimal(prezzo))
                righe += 1
        self.stdout.write(f"  Listini fornitori: {len(listini)} con {righe} voci")

    # --------------------------------------------------------------- cantieri
    def _cantieri(self):
        oggi = timezone.localdate()
        for nome, via, cap, citta, prov, stato, cliente_nome in CANTIERI:
            cliente = self.clienti.get(cliente_nome)
            cantiere = Job.objects.create(
                name=nome,
                customer=cliente,
                status=stato,
                address=via,
                zip_code=cap,
                city=citta,
                province=prov,
                start_date=oggi - timedelta(days=self.casuale.randint(10, 180)),
                end_date=oggi + timedelta(days=self.casuale.randint(5, 60)) if stato in Job.OPEN_STATUSES else None,
                notes=f"Rif. {cliente_nome}. Accesso dal cortile, orari 8:00-17:00.",
            )
            self.cantieri[nome] = cantiere

        # manutenzioni programmate (piscine e caldaie)
        piscina = self.cantieri["Manutenzione piscina Centro Sportivo Orobico"]
        MaintenancePlan.objects.create(
            name="Manutenzione mensile piscina - controllo acqua e filtri",
            customer=piscina.customer,
            job=piscina,
            frequency=MaintenancePlan.FREQUENCY_MONTHLY,
            next_date=oggi + timedelta(days=6),
            notes="Controllo cloro/pH, pulizia filtri e robot.",
        )
        villa = self.cantieri["Villa privata con piscina - Scanzorosciate"]
        MaintenancePlan.objects.create(
            name="Apertura stagionale piscina",
            customer=villa.customer,
            job=villa,
            frequency=MaintenancePlan.FREQUENCY_ANNUAL,
            next_date=oggi + timedelta(days=25),
            notes="Apertura, avvio impianto e trattamento di avvio.",
        )
        MaintenancePlan.objects.create(
            name="Chiusura stagionale piscina",
            customer=villa.customer,
            job=villa,
            frequency=MaintenancePlan.FREQUENCY_ANNUAL,
            next_date=oggi + timedelta(days=180),
            notes="Invernaggio e copertura.",
        )
        self.stdout.write(f"  Cantieri: {len(self.cantieri)} con 3 manutenzioni programmate")

    # -------------------------------------------------------------- modelli
    def _modelli(self):
        if QuoteTemplate.objects.exists():
            return
        bagno = QuoteTemplate.objects.create(
            name="Bagno completo - composizione base",
            description="Sanitari, mobile, rubinetteria e posa in opera",
            payment_term=self.rif["pagamenti"]["Bonifico 30 giorni"],
            terms_text=(
                "Validità dell'offerta 30 giorni.\n"
                "<b>Posa in opera inclusa</b>; smaltimento materiali a parte.\n"
                "Tempi di consegna: 3-4 settimane dall'ordine."
            ),
            notes="Modello da adattare alle misure del bagno.",
            sort_order=1,
        )
        righe_bagno = [
            ("Sanitari", "wc sospeso + bidet + sedile soft close", "1", "780.00"),
            ("Mobile bagno", "mobile lavabo 2 cassetti l=90 + specchio led", "1", "1090.00"),
            ("Rubinetteria", "miscelatore lavabo + miscelatore bidet + doccia", "1", "520.00"),
            ("Posa", "montaggio e posa in opera", "16", "45.00"),
        ]
        for posizione, (sezione, descrizione, quantita, prezzo) in enumerate(righe_bagno, start=1):
            QuoteTemplateLine.objects.create(
                template=bagno, position=posizione, section=sezione, description=descrizione,
                qty=Decimal(quantita), uom=self.rif["ore"] if sezione == "Posa" else self.rif["pz"],
                unit_price=Decimal(prezzo), vat_rate=self.rif["vat22"],
            )

        piscina = QuoteTemplate.objects.create(
            name="Piscina - apertura e chiusura stagionale",
            description="Manutenzione stagionale con prodotti inclusi",
            payment_term=self.rif["pagamenti"]["Rimessa diretta"],
            terms_text="Interventi programmati su appuntamento.\nProdotti chimici inclusi.",
            sort_order=2,
        )
        for posizione, descrizione in enumerate(
            ("apertura piscina (pulizia, avvio impianto, trattamento)", "chiusura piscina e invernaggio", "interventi in cantiere")
        , start=1):
            QuoteTemplateLine.objects.create(
                template=piscina, position=posizione, description=descrizione,
                qty=Decimal("1"), uom=self.rif["pz"], unit_price=Decimal("350.00"), vat_rate=self.rif["vat22"],
            )

    # ------------------------------------------------------------- preventivi
    def _preventivi(self):
        self._modelli()
        oggi = timezone.localdate()
        pz, ore = self.rif["pz"], self.rif["ore"]
        termini = (
            "Pagamento: come concordato.\n"
            "Prezzi IVA esclusa salvo diversa indicazione.\n"
            "Validità dell'offerta 30 giorni."
        )
        agenti = [self.clienti[nome] for nome, *_ in AGENTI]

        # (cliente, stato, giorni fa, righe, provvigione %, cantiere)
        bagno_base = [
            ("Sanitari", "Vaso sospeso scarico A-SOUND bianco lucido", "0201801", "1", "315.00", "10"),
            ("Sanitari", "Bidet sospeso bianco lucido", "0202001", "1", "294.00", "10"),
            ("Sanitari", "Sedile soft closing sgancio rapido", "339101", "1", "91.00", "10"),
            ("Mobile", "Mobile lavabo 2 cassetti l=90 con piano", "CS1040904840", "1", "912.00", "15"),
            ("Mobile", "Specchio con luce LED l=120", "BALDO", "1", "272.00", "15"),
            ("Rubinetteria", "Miscelatore lavabo con piletta clic-clack", "JAG91D1", "1", "165.00", "20"),
            ("Rubinetteria", "Miscelatore bidet con piletta", "JAG94D1", "1", "192.00", "20"),
            ("Doccia", "Set doccia con braccio e soffione", "24161000", "1", "128.00", "20"),
            ("Posa", "Montaggio e posa in opera", "MONTAGGIO", "12", "45.00", "0"),
        ]
        bagno_grande = [
            ("Sanitari", "Vaso sospeso A-SOUND + bidet + sedile", "0201801", "2", "315.00", "10"),
            ("Mobile", "Base lavabo 2 cassetti l=120", "CS1040904840", "2", "912.00", "18"),
            ("Top", "Piano in gres su misura al metro lineare", "PROGETTO", "2", "450.00", "0"),
            ("Box doccia", "Box doccia scorrevole 140x80 cristallo 6mm", "DEB.140.80", "2", "740.00", "22"),
            ("Piatti doccia", "Piatto doccia 170x90 texture ardesia", "DPL.17090", "2", "523.00", "22"),
            ("Rubinetteria", "Miscelatore lavabo PVD copper", "E214015.CO316", "2", "389.00", "25"),
            ("Scaldasalviette", "Scaldasalviette elettrico l=500 h=1100", "351356100238.R01", "2", "498.00", "20"),
            ("Posa", "Posa in opera idraulica", "POSA.IDR", "24", "48.00", "0"),
            ("Posa", "Posa piastrelle e rivestimenti", "POSA.PIAST", "30", "42.00", "0"),
        ]
        piscina_righe = [
            ("Piscina", "Pompa di ricircolo autoadescante 400 W", "PMP.SPEED400", "1", "289.00", "5"),
            ("Piscina", "Filtro a sabbia d.500 con valvola 6 vie", "FILT.SAND500", "1", "395.00", "5"),
            ("Piscina", "Cloro multiazione 5 kg", "CLORO.MULTI5", "4", "48.00", "0"),
            ("Servizi", "Apertura piscina stagionale", "APERTURA.PISC", "1", "350.00", "0"),
        ]

        preventivi = [
            ("Famiglia Ferrari", Quote.STATUS_DRAFT, 3, bagno_grande, "0", "Villa privata con piscina - Scanzorosciate"),
            ("Condominio Le Vele", Quote.STATUS_SENT, 6, bagno_grande, "3", "Complesso residenziale Le Vele - 6 bagni"),
            ("Impresa Edile Fratelli Locatelli snc", Quote.STATUS_SENT, 9, bagno_base, "0", "Bagno di servizio uffici Locatelli"),
            ("B&B Il Giardino Segreto", Quote.STATUS_ACCEPTED, 14, bagno_base, "2", "Rifacimento bagni B&B Il Giardino Segreto"),
            ("Centro Sportivo Orobico", Quote.STATUS_SENT, 11, piscina_righe, "5", "Manutenzione piscina Centro Sportivo Orobico"),
            ("Stefano Riva", Quote.STATUS_ACCEPTED, 18, bagno_base, "0", None),
            ("Giulia Moretti", Quote.STATUS_REJECTED, 25, bagno_base, "0", None),
            ("Laura Bianchi", Quote.STATUS_ACCEPTED, 21, bagno_grande, "0", None),
            ("Andrea Colombo", Quote.STATUS_DRAFT, 1, bagno_base, "0", None),
            ("Agriturismo Cascina Nova", Quote.STATUS_SENT, 8, piscina_righe, "3", None),
            ("Tenuta Sant'Ambrogio", Quote.STATUS_DRAFT, 2, bagno_grande, "0", None),
            ("Amministrazione Palazzo Aurora", Quote.STATUS_SENT, 16, bagno_grande, "2", None),
            ("Dental Center Dr. Parisi", Quote.STATUS_ACCEPTED, 30, bagno_base, "0", None),
            ("Beauty & Spa Aurora srl", Quote.STATUS_ACCEPTED, 40, bagno_grande, "0", "Bagno Beauty & Spa Aurora"),
            ("Rifugio La Baita snc", Quote.STATUS_REJECTED, 45, piscina_righe, "0", None),
            ("Marco Rossi", Quote.STATUS_ACCEPTED, 60, bagno_base, "0", "Ristrutturazione bagno Via Verdi"),
        ]

        creati = 0
        for indice, (cliente_nome, stato, giorni_fa, righe, provvigione, cantiere_nome) in enumerate(preventivi):
            cliente = self.clienti[cliente_nome]
            data = oggi - timedelta(days=giorni_fa)
            preventivo = Quote.objects.create(
                date=data,
                valid_until=data + timedelta(days=30),
                customer=cliente,
                job=self.cantieri.get(cantiere_nome),
                payment_term=cliente.payment_term or self.rif["pagamenti"]["Bonifico 30 giorni"],
                status=stato,
                reference="Rif. " + str(1000 + indice) if indice % 2 else "",
                terms_text=termini,
                notes="Cliente seguito in fase di scelta dei materiali." if indice % 4 == 0 else "",
                commission_contact=agenti[indice % len(agenti)] if Decimal(provvigione) > 0 else None,
                commission_pct=Decimal(provvigione),
            )
            self._righe_preventivo(preventivo, righe)
            creati += 1

        self.stdout.write(f"  Preventivi: {creati} in stati diversi (bozza, inviato, accettato, rifiutato)")

    def _righe_preventivo(self, preventivo, righe):
        posizione = 0
        for sezione, descrizione, codice, quantita, prezzo, sconto in righe:
            articolo = self.articoli.get(codice)
            posizione += 1
            QuoteLine.objects.create(
                quote=preventivo,
                position=posizione,
                section=sezione,
                product=articolo,
                description=descrizione,
                qty=Decimal(quantita),
                uom=articolo.uom if articolo else self.rif["pz"],
                unit_price=Decimal(prezzo),
                discount_pct=Decimal(sconto),
                vat_rate=self.rif["vat22"],
            )
        preventivo.recalculate()

    # -------------------------------------------------------- ordini cliente
    def _ordini_cliente(self):
        """Trasforma i preventivi accettati in ordini confermati.

        La consegna avviene dopo, con i DDT: è il flusso normale dell'ufficio.
        """
        oggi = timezone.localdate()
        creati = 0
        for preventivo in Quote.objects.filter(status=Quote.STATUS_ACCEPTED).order_by("date"):
            ordine = sales_services.convert_quote_to_order(preventivo)
            ordine.status = SalesOrder.STATUS_CONFIRMED
            ordine.expected_date = ordine.date + timedelta(days=21)
            ordine.save(update_fields=["status", "expected_date"])
            creati += 1

        # due ordini creati direttamente, senza preventivo
        for indice, (cliente_nome, stato) in enumerate(
            (("Hotel Villa Serena srl", SalesOrder.STATUS_CONFIRMED), ("Studio Architettura Bertoni", SalesOrder.STATUS_DRAFT))
        ):
            cliente = self.clienti[cliente_nome]
            ordine = SalesOrder.objects.create(
                date=oggi - timedelta(days=indice),
                customer=cliente,
                job=self.cantieri.get("Bagno Hotel Villa Serena - camere 1-3 piano" if indice == 0 else None),
                payment_term=cliente.payment_term,
                status=stato,
                reference="Ordine diretto",
                notes="Ordine ricevuto per telefono, da confermare con il cliente.",
                expected_date=oggi + timedelta(days=20),
                commission_contact=self.clienti[AGENTI[indice][0]],
                commission_pct=Decimal("3.5") if indice == 0 else Decimal("2"),
            )
            SalesOrderLine.objects.create(
                order=ordine, position=1, product=self.articoli["DEB.100.70"],
                description="Box doccia scorrevole 100x70", qty=Decimal("3"),
                uom=self.rif["pz"], unit_price=Decimal("640.00"), discount_pct=Decimal("10"), vat_rate=self.rif["vat22"],
            )
            SalesOrderLine.objects.create(
                order=ordine, position=2, product=self.articoli["MONTAGGIO"],
                description="Montaggio e posa in opera", qty=Decimal("6"),
                uom=self.rif["ore"], unit_price=Decimal("45.00"), vat_rate=self.rif["vat22"],
            )
            ordine.recalculate()
            creati += 1

        self.stdout.write(f"  Ordini cliente: {creati} (da consegnare, in attesa di DDT)")

    # ------------------------------------------------------- ordini fornitore
    def _ordini_fornitore(self):
        oggi = timezone.localdate()
        # (fornitore, stato, giorni fa, righe (codice, quantita))
        ordini = [
            ("We Do Home srl", PurchaseOrder.STATUS_CONFIRMED, 6, [("E214015.CO316", "2"), ("CAPSULA.60120", "3"), ("BALDO", "2")]),
            ("Novellini spa", PurchaseOrder.STATUS_CONFIRMED, 4, [("DEB.140.80", "2"), ("KUADH120-1H", "1"), ("DPL.17090", "2")]),
            ("Azzurra Sanitari in Ceramica spa", PurchaseOrder.STATUS_CONFIRMED, 9, [("0201801", "4"), ("0202001", "4"), ("339101", "6")]),
            ("Lacus srl", PurchaseOrder.STATUS_RECEIVED, 20, [("JAG91D1", "6"), ("JAG94D1", "6"), ("BE022AA", "4")]),
            ("Hansgrohe srl", PurchaseOrder.STATUS_RECEIVED, 32, [("24161000", "5"), ("37059000", "3"), ("37859000", "4")]),
            ("Cordivari srl", PurchaseOrder.STATUS_RECEIVED, 45, [("351356100238.R01", "2"), ("3551626102064", "2")]),
            ("Geda srl", PurchaseOrder.STATUS_CONFIRMED, 2, [("CLORO.MULTI5", "8"), ("BOMBOLA.PH", "6"), ("FILT.SAND500", "1")]),
            ("Almar srl", PurchaseOrder.STATUS_DRAFT, 1, [("WQO13.08", "6"), ("EQO06/11DX.08", "4")]),
            ("Colavene srl", PurchaseOrder.STATUS_RECEIVED, 55, [("540388", "20"), ("AF0004", "8")]),
            ("We Do Home srl", PurchaseOrder.STATUS_DRAFT, 0, [("KAYRA.90.80", "2"), ("THEMIS.105.70", "2")]),
        ]
        ricevuti = 0
        for fornitore_nome, stato, giorni_fa, righe in ordini:
            fornitore = self.fornitori[fornitore_nome]
            ordine = PurchaseOrder.objects.create(
                date=oggi - timedelta(days=giorni_fa),
                supplier=fornitore,
                status=stato if stato != PurchaseOrder.STATUS_RECEIVED else PurchaseOrder.STATUS_CONFIRMED,
                notes=f"Rif. fornitore: {self.casuale.randint(10000, 99999)}",
            )
            for posizione, (codice, quantita) in enumerate(righe, start=1):
                articolo = self.articoli.get(codice)
                if articolo is None:
                    continue
                PurchaseOrderLine.objects.create(
                    po=ordine, position=posizione, product=articolo,
                    description=articolo.name, qty=Decimal(quantita),
                    uom=articolo.uom, unit_price=articolo.purchase_price or ZERO,
                    discount_pct=Decimal(self.casuale.choice(["0", "0", "10", "20"])),
                    vat_rate=self.rif["vat22"],
                )
            ordine.recalculate()
            if stato == PurchaseOrder.STATUS_RECEIVED:
                for riga in ordine.lines.all():
                    riga.qty_received = riga.qty
                    riga.save(update_fields=["qty_received"])
                    if riga.product and riga.product.is_stock_tracked:
                        register_movement(
                            product=riga.product, delta=riga.qty, movement_type=StockMovement.TYPE_LOAD,
                            reference=ordine.number, note=f"Ricezione {ordine.number}", unit_cost=riga.unit_cost,
                        )
                ordine.status = PurchaseOrder.STATUS_RECEIVED
                ordine.save(update_fields=["status"])
                ricevuti += 1

        self.stdout.write(f"  Ordini fornitore: {len(ordini)} (di cui {ricevuti} ricevuti con carico a magazzino)")

    def _rifornisci_per_consegna(self, nota):
        """Se in magazzino non c'è abbastanza, carica la merce mancante.

        Nel mondo reale la merce arriva dal fornitore prima della consegna: qui
        si registra un carico, così il DDT si può emettere senza andare in
        giacenza negativa.
        """
        for riga in nota.lines.select_related("product"):
            prodotto = riga.product
            if prodotto is None or not prodotto.is_stock_tracked:
                continue
            mancante = Decimal(riga.qty or 0) - prodotto.total_stock
            if mancante > 0:
                register_movement(
                    product=prodotto,
                    delta=mancante,
                    movement_type=StockMovement.TYPE_LOAD,
                    reference=nota.number,
                    note=f"Rifornimento per la consegna {nota.number}",
                    unit_cost=prodotto.purchase_price or None,
                )

    # -------------------------------------------------------------------- DDT
    def _ddt(self):
        """Prepara i DDT degli ordini confermati e ne emette buona parte.

        Emettere il DDT scarica il magazzino e segna l'ordine come consegnato:
        la consegna viene poi retrodatata, così le statistiche hanno una storia.
        """
        oggi = timezone.localdate()
        ordini = list(SalesOrder.objects.filter(status=SalesOrder.STATUS_CONFIRMED).order_by("date"))
        emessi = bozze = 0
        for indice, ordine in enumerate(ordini):
            nota = billing_services.create_delivery_note_from_order(ordine)
            if indice % 3 == 2:  # ogni tanto il DDT resta in bozza, da completare
                bozze += 1
                continue
            self._rifornisci_per_consegna(nota)
            errori = billing_services.issue_delivery_note(nota)
            if errori:
                self.stderr.write(f"    DDT {nota.number}: {errori[0]}")
                continue
            # retrodato la consegna: da qualche giorno a qualche mese fa
            quando = oggi - timedelta(days=self.casuale.randint(4, 210))
            momento = timezone.make_aware(
                timezone.datetime.combine(quando, timezone.datetime.min.time())
            ) + timedelta(hours=self.casuale.randint(8, 17))
            ordine.delivered_at = momento
            ordine.date = min(ordine.date, quando - timedelta(days=7))
            ordine.save(update_fields=["delivered_at", "date"])
            nota.issued_at = momento
            nota.date = quando
            nota.save(update_fields=["issued_at", "date"])
            emessi += 1

        self.stdout.write(f"  DDT: {emessi} emessi (consegne registrate) e {bozze} in bozza")

    def _provvigioni_del_mese(self):
        """Assicura che il mese corrente abbia provvigioni da mostrare.

        La pagina «Provvigioni» si apre sul mese in corso: se il caso ha portato
        le provvigioni tutte nei mesi passati, ne assegna una a un ordine
        confermato di oggi.
        """
        oggi = timezone.localdate()
        esiste = SalesOrder.objects.filter(
            commission_contact__isnull=False,
            status__in=(SalesOrder.STATUS_CONFIRMED, SalesOrder.STATUS_DELIVERED),
        ).filter(date__year=oggi.year, date__month=oggi.month).exists()
        if esiste:
            return
        ordine = SalesOrder.objects.filter(status=SalesOrder.STATUS_CONFIRMED).order_by("-date").first()
        if ordine is None:
            return
        ordine.commission_contact = self.clienti[AGENTI[0][0]]
        ordine.commission_pct = Decimal("3")
        ordine.save(update_fields=["commission_contact", "commission_pct"])
        self.stdout.write(f"  Provvigione del mese assegnata all'ordine {ordine.number}")

    # ----------------------------------------------------------------- fatture
    def _fatture(self):
        emesse = incassate = 0
        for indice, ordine in enumerate(SalesOrder.objects.filter(status=SalesOrder.STATUS_DELIVERED).order_by("delivered_at")):
            if SalesInvoice.objects.filter(source_order=ordine).exists():
                continue
            fattura = billing_services.create_sales_invoice_from_order(ordine, only_delivered=True)
            if fattura is None or not fattura.lines.exists():
                continue
            fattura.date = (ordine.delivered_at or timezone.now()).date() + timedelta(days=2)
            fattura.save(update_fields=["date"])
            if indice % 4 != 3:
                billing_services.issue_sales_invoice(fattura)
                emesse += 1
                if indice % 3 == 0:
                    billing_services.mark_sales_invoice_sent(fattura)
                if indice % 4 == 0:
                    billing_services.mark_sales_invoice_paid(fattura)
                    incassate += 1
            else:
                emesse += 1

        ricevute = 0
        for ordine in PurchaseOrder.objects.filter(status=PurchaseOrder.STATUS_RECEIVED)[:4]:
            if PurchaseInvoice.objects.filter(source_po=ordine).exists():
                continue
            fattura = billing_services.create_purchase_invoice_from_po(ordine, only_received=True)
            if fattura is None or not fattura.lines.exists():
                continue
            fattura.date = (ordine.date + timedelta(days=5))
            fattura.save(update_fields=["date"])
            billing_services.register_purchase_invoice(fattura)
            if ricevute % 2 == 0:
                billing_services.mark_purchase_invoice_paid(fattura)
            ricevute += 1

        self.stdout.write(f"  Fatture: {emesse} emesse (di cui {incassate} incassate) e {ricevute} ricevute")

    # ------------------------------------------------------------ manutenzioni
    def _manutenzioni(self):
        pass  # create insieme ai cantieri

    # --------------------------------------------------------------- personale
    def _personale(self):
        oggi = timezone.localdate()
        persone = [
            ("Luca", "Bianchi", "Idraulico", Decimal("22.50")),
            ("Sara", "Rossi", "Impiegata ufficio", Decimal("18.00")),
            ("Marco", "Ferrari", "Elettricista", Decimal("21.00")),
            ("Davide", "Galli", "Piastrellista", Decimal("20.00")),
        ]
        dipendenti = []
        for nome, cognome, mansione, costo in persone:
            dipendente = Employee.objects.create(
                first_name=nome, last_name=cognome, qualification=mansione,
                hourly_cost=costo, contract_weekly_hours=Decimal("40"),
                holiday_days_per_year=Decimal("26"), rol_hours_per_year=Decimal("40"),
                hired_on=oggi.replace(year=oggi.year - 2, month=3, day=1),
                email=f"{nome.lower()}.{cognome.lower()}@aquaforma.example.it",
                phone=f"3{self.casuale.randint(30, 49)} {self.casuale.randint(1000000, 9999999)}",
            )
            dipendenti.append(dipendente)

        cantieri_attivi = [c for c in self.cantieri.values() if c.status in Job.OPEN_STATUSES][:4]
        # due mesi di ore lavorate, 8 ore al giorno dal lunedì al venerdì
        for indice, dipendente in enumerate(dipendenti):
            for giorno_fa in range(60):
                giorno = oggi - timedelta(days=giorno_fa)
                if giorno.weekday() >= 5:
                    continue
                cantiere = cantieri_attivi[(giorno_fa + indice) % len(cantieri_attivi)]
                ore = Decimal("8") if (giorno_fa % 7) else Decimal("6")
                TimeEntry.objects.create(
                    employee=dipendente, date=giorno, hours=ore,
                    kind=TimeEntry.KIND_ORDINARY, job=cantiere,
                    description="Installazione e montaggio in cantiere", billable=True,
                )
            TimeEntry.objects.create(
                employee=dipendente, date=oggi - timedelta(days=2), hours=Decimal("3"),
                kind=TimeEntry.KIND_OVERTIME, job=cantieri_attivi[indice % len(cantieri_attivi)],
                description="Straordinario per consegna urgente",
            )

        # ferie e permessi in stati diversi
        richiesta = LeaveRequest.objects.create(
            employee=dipendenti[1], kind=LeaveRequest.KIND_HOLIDAY,
            start_date=oggi + timedelta(days=10), end_date=oggi + timedelta(days=16),
            reason="Vacanza programmata", created_by=None,
        )
        LeaveRequest.objects.create(
            employee=dipendenti[2], kind=LeaveRequest.KIND_ROL,
            start_date=oggi + timedelta(days=3), end_date=oggi + timedelta(days=3), hours=Decimal("3"),
            reason="Visita medica",
        )
        approvata = LeaveRequest.objects.create(
            employee=dipendenti[0], kind=LeaveRequest.KIND_HOLIDAY,
            start_date=oggi - timedelta(days=30), end_date=oggi - timedelta(days=24),
            reason="Ferie estive",
        )
        approvata.approve(None)
        LeaveRequest.objects.create(
            employee=dipendenti[3], kind=LeaveRequest.KIND_SICK,
            start_date=oggi - timedelta(days=9), end_date=oggi - timedelta(days=7),
            reason="Influenza",
        ).approve(None)

        self.stdout.write(f"  Personale: {len(dipendenti)} dipendenti, ore degli ultimi 2 mesi e 4 richieste di assenza")
        self._richiesta_da_approvare = richiesta

    # ------------------------------------------------------------ collaboratori
    def _collaboratori(self):
        oggi = timezone.localdate()
        persone = [
            ("Mario Scavi", "Scavi Bianchi", "scavo e movimento terra", Decimal("32.00"), "demo.collaboratore"),
            ("Elettricista Verdi", "Verdi Impianti", "elettricista", Decimal("38.00"), None),
            ("Piastrellista Neri", "Neri Pavimenti", "piastrellista", Decimal("35.00"), None),
        ]
        cantieri_attivi = [c for c in self.cantieri.values() if c.status in Job.OPEN_STATUSES][:4]
        collaboratori = []
        for indice, (nome, ditta, specializzazione, tariffa, username) in enumerate(persone):
            utente = get_user_model().objects.filter(username=username).first() if username else None
            collaboratore = Collaborator.objects.create(
                name=nome, company=ditta, specialization=specializzazione,
                hourly_rate=tariffa, user=utente,
                phone=f"3{self.casuale.randint(30, 49)} {self.casuale.randint(1000000, 9999999)}",
                email=f"{nome.split()[0].lower()}@{ditta.split()[0].lower()}.example.it",
                notes="Collaboratore esterno: rendiconta le ore dal gestionale." if utente else "",
            )
            collaboratori.append(collaboratore)
            for giorno_fa in range(24):
                giorno = oggi - timedelta(days=giorno_fa)
                if giorno.weekday() >= 5 or giorno_fa % 3 == 2:
                    continue
                CollaboratorTimeEntry.objects.create(
                    collaborator=collaboratore, date=giorno,
                    hours=Decimal(self.casuale.choice(["4", "6", "8"])),
                    job=cantieri_attivi[(giorno_fa + indice) % len(cantieri_attivi)],
                    description=f"{specializzazione.capitalize()} in cantiere",
                )
        self.stdout.write(f"  Collaboratori: {len(collaboratori)} con le ore degli ultimi giorni")

    # -------------------------------------------------------------------- foto
    def _foto(self):
        """Genera qualche foto di cantiere e qualche bolla, per provare la sezione."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return

        cantieri_foto = list(self.cantieri.values())[:3]
        collaboratori = list(Collaborator.objects.all()[:2])
        if not cantieri_foto or not collaboratori:
            return

        def immagine(testo, colore, sotto="Aquaforma srl · dati dimostrativi"):
            larghezza, altezza = 1600, 1200
            tela = Image.new("RGB", (larghezza, altezza), colore)
            disegno = ImageDraw.Draw(tela)
            disegno.rectangle([(0, 0), (larghezza - 1, altezza - 1)], outline=(255, 255, 255), width=8)
            disegno.rectangle([(0, altezza - 260), (larghezza, altezza)], fill=(29, 44, 56))
            disegno.text((60, altezza - 190), testo, fill=(255, 255, 255))
            disegno.text((60, altezza - 120), sotto, fill=(138, 185, 177))
            buffer = BytesIO()
            tela.save(buffer, format="JPEG", quality=80)
            return ContentFile(buffer.getvalue(), name="foto.jpg")

        create = 0
        for indice, cantiere in enumerate(cantieri_foto):
            for momento, colore in (("inizio giornata", (120, 144, 156)), ("fine giornata", (144, 164, 174))):
                foto = Attachment(
                    name=f"{cantiere.name[:40]} - {momento}",
                    kind=Attachment.KIND_SITE,
                    job=cantiere,
                    collaborator=collaboratori[indice % len(collaboratori)],
                    notes=f"Foto {momento}",
                )
                foto.file.save(f"cantiere_{indice}_{momento.split()[0]}.jpg", immagine(momento.upper(), colore), save=True)
                create += 1

        for indice, (fornitore, importo) in enumerate((("Ferramenta Bergamasca snc", "248,50"), ("Geda srl", "612,00"))):
            bolla = Attachment(
                name=f"Bolla {fornitore} - {importo} EUR",
                kind=Attachment.KIND_RECEIPT,
                collaborator=collaboratori[indice % len(collaboratori)],
                notes=f"Acquisto materiale di consumo · {importo} €",
            )
            bolla.file.save(f"bolla_{indice}.jpg", immagine(f"BOLLA {fornitore.upper()}", (146, 152, 160)), save=True)
            create += 1

        self.stdout.write(f"  Foto: {create} immagini (cantieri e bolle) nella sezione «Foto e bolle»")

    # ---------------------------------------------------------------- riepilogo
    def _riepilogo(self):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Dati dimostrativi pronti."))
        self.stdout.write(f"  Clienti: {Contact.objects.filter(is_customer=True).count()}")
        self.stdout.write(f"  Fornitori: {Contact.objects.filter(is_supplier=True).count()}")
        self.stdout.write(f"  Articoli: {Product.objects.count()}")
        self.stdout.write(f"  Preventivi: {Quote.objects.count()}")
        self.stdout.write(f"  Ordini cliente: {SalesOrder.objects.count()}")
        self.stdout.write(f"  Ordini fornitore: {PurchaseOrder.objects.count()}")
        self.stdout.write(f"  DDT: {DeliveryNote.objects.count()}")
        self.stdout.write(f"  Fatture emesse: {SalesInvoice.objects.count()} · ricevute: {PurchaseInvoice.objects.count()}")
        self.stdout.write(f"  Cantieri: {Job.objects.count()} · manutenzioni: {MaintenancePlan.objects.count()}")
        self.stdout.write(f"  Dipendenti: {Employee.objects.count()} · collaboratori: {Collaborator.objects.count()}")
        self.stdout.write("")
        self.stdout.write("  Utenti per provare i ruoli (password: %s):" % PASSWORD_DEMO)
        for username, gruppo, azione in self.utenti_demo:
            self.stdout.write(f"    {username:<22} ruolo {gruppo}")

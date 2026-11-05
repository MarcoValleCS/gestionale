"""Costanti condivise dei contenuti della guida."""

# Ruoli del gestionale (nomi dei Group Django)
ADMIN = "Amministratore"
VENDITE = "Vendite"
ACQUISTI = "Acquisti"
MAGAZZINO = "Magazzino"
PERSONALE = "Personale"
COLLABORATORE = "Collaboratore"

# Pagine per tutti gli utenti autenticati
TUTTI = ""

# Ufficio: chi vede l'area commerciale/amministrativa (escluso il collaboratore)
UFFICIO = "Vendite, Acquisti, Magazzino, Personale, Amministratore"

# Gruppi di ruoli usati nelle singole pagine
SOLO_ADMIN = ADMIN
SOLO_VENDITE = f"{VENDITE}, {ADMIN}"
SOLO_ACQUISTI = f"{ACQUISTI}, {ADMIN}"
SOLO_MAGAZZINO = f"{MAGAZZINO}, {ADMIN}"
SOLO_PERSONALE = f"{PERSONALE}, {ADMIN}"
SOLO_COLLABORATORE = f"{COLLABORATORE}, {ADMIN}"
VENDITE_ACQUISTI = f"{VENDITE}, {ACQUISTI}, {ADMIN}"
VENDITE_MAGAZZINO = f"{VENDITE}, {MAGAZZINO}, {ADMIN}"
VENDITE_PERSONALE = f"{VENDITE}, {PERSONALE}, {ADMIN}"
ACQUISTI_MAGAZZINO = f"{ACQUISTI}, {MAGAZZINO}, {ADMIN}"

# Chi può consultare le anagrafiche senza modificarle
CONSULTAZIONE = f"{MAGAZZINO}, {PERSONALE}, {ADMIN}"
# Aree che possono avere allegati (articoli e cantieri)
ALLEGATI = f"{VENDITE}, {ACQUISTI}, {MAGAZZINO}, {ADMIN}"
# Casella aziendale
POSTA = f"{VENDITE}, {ACQUISTI}, {PERSONALE}, {ADMIN}"

COMMERCIALE = f"{VENDITE}, {ACQUISTI}, {MAGAZZINO}, {ADMIN}"
UFFICIO_COMPLETO = f"{VENDITE}, {ACQUISTI}, {MAGAZZINO}, {PERSONALE}, {ADMIN}"

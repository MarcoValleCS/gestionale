"""Rapportini dei collaboratori: invio, conferma, rimborsi e costi di cantiere.

La logica sta qui e non nelle viste, come per vendite, acquisti e magazzino:
le pagine del collaboratore, quelle dell'ufficio e (in futuro) gli strumenti
MCP chiamano le stesse funzioni.
"""
from collections import OrderedDict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.cache import dimentica, memoizza
from apps.core.concurrency import aggiorna_se
from apps.core.models import Attachment
from apps.core.rounding import round2

from .models import CollaboratorExpense, CollaboratorTimeEntry

ZERO = Decimal("0")
CHIAVE_BADGE = "badge_rapportini"


def _allegato(file, *, kind, entry, user, notes=""):
    """Salva una foto o uno scontrino come allegato del rapportino.

    Passa da ``Attachment``: le foto vengono raddrizzate e compresse e il
    collaboratore potrà riaprirle (le vede solo lui e l'ufficio).
    """
    allegato = Attachment(
        file=file,
        kind=kind,
        collaborator=entry.collaborator,
        job=entry.job,
        report=entry,
        notes=(notes or "")[:200],
        uploaded_by=user,
    )
    allegato.save()
    return allegato


def _elimina_allegato(allegato):
    if allegato is None:
        return
    allegato.file.delete(save=False)
    allegato.delete()


@transaction.atomic
def salva_rapportino(entry, spese_formset=None, foto=(), user=None):
    """Salva il rapportino del collaboratore e lo (ri)mette in coda all'ufficio.

    ``entry`` è il rapportino già compilato dal form (non ancora salvato o
    modificato). Ogni invio, anche una correzione dopo un «da correggere»,
    lo riporta fra quelli da confermare. Le spese arrivano dal formset, con lo
    scontrino eventualmente fotografato; le foto del cantiere sono una lista
    di file.
    """
    if entry.pk and entry.status == CollaboratorTimeEntry.STATUS_APPROVED:
        raise ValidationError("Il rapportino è già stato confermato dall'ufficio: non si può più modificare.")
    if entry.pk is None and user is not None:
        entry.created_by = user
    entry.status = CollaboratorTimeEntry.STATUS_SUBMITTED
    entry.reviewed_by = None
    entry.reviewed_at = None
    entry.save()

    # Le foto e gli scontrini seguono il cantiere del rapportino.
    entry.attachments.exclude(job_id=entry.job_id).update(job_id=entry.job_id)

    if spese_formset is not None:
        for form in spese_formset.forms:
            if not form.has_changed() and form.instance.pk is None:
                continue
            spesa = form.instance
            if spese_formset.can_delete and form.cleaned_data.get("DELETE"):
                if spesa.pk:
                    ricevuta = spesa.receipt
                    spesa.delete()
                    _elimina_allegato(ricevuta)
                continue
            spesa = form.save(commit=False)
            spesa.entry = entry
            scontrino = form.cleaned_data.get("scontrino")
            if scontrino:
                vecchio = spesa.receipt
                spesa.receipt = _allegato(
                    scontrino,
                    kind=Attachment.KIND_RECEIPT,
                    entry=entry,
                    user=user,
                    notes=spesa.description or spesa.get_category_display(),
                )
                spesa.save()
                _elimina_allegato(vecchio)
            else:
                spesa.save()

    for file in foto or ():
        _allegato(file, kind=Attachment.KIND_SITE, entry=entry, user=user)

    dimentica(CHIAVE_BADGE)
    return entry


@transaction.atomic
def elimina_rapportino(entry):
    """Cancella il rapportino con spese, foto e scontrini (file compresi)."""
    if entry.status == CollaboratorTimeEntry.STATUS_APPROVED:
        raise ValidationError("Il rapportino è già stato confermato dall'ufficio: non si può più cancellare.")
    for allegato in list(entry.attachments.all()):
        _elimina_allegato(allegato)
    entry.delete()
    dimentica(CHIAVE_BADGE)


def conferma_rapportino(entry, user):
    """L'ufficio conferma il rapportino: ore e spese entrano nei costi.

    Il cambio di stato è un UPDATE condizionato: due conferme contemporanee
    (doppio clic, due persone in ufficio) non si sovrappongono.
    """
    with transaction.atomic():
        fatto = aggiorna_se(
            entry,
            Q(status__in=[CollaboratorTimeEntry.STATUS_SUBMITTED, CollaboratorTimeEntry.STATUS_REJECTED]),
            status=CollaboratorTimeEntry.STATUS_APPROVED,
            reviewed_by=user,
            reviewed_at=timezone.now(),
            review_note="",
        )
    if not fatto:
        raise ValidationError("Il rapportino risulta già confermato.")
    dimentica(CHIAVE_BADGE)
    return entry


def rimanda_rapportino(entry, user, nota):
    """L'ufficio rimanda indietro il rapportino con una nota da correggere.

    Vale anche per un rapportino già confermato, purché nessuna sua spesa sia
    già stata rimborsata (altrimenti il rimborso non tornerebbe più).
    """
    nota = (nota or "").strip()
    if not nota:
        raise ValidationError("Scrivi cosa va corretto: il collaboratore vedrà la nota.")
    if entry.expenses.filter(reimbursed_at__isnull=False).exists():
        raise ValidationError("Alcune spese sono già state rimborsate: il rapportino non si può riaprire.")
    with transaction.atomic():
        fatto = aggiorna_se(
            entry,
            Q(status__in=[CollaboratorTimeEntry.STATUS_SUBMITTED, CollaboratorTimeEntry.STATUS_APPROVED]),
            status=CollaboratorTimeEntry.STATUS_REJECTED,
            reviewed_by=user,
            reviewed_at=timezone.now(),
            review_note=nota[:300],
        )
    if not fatto:
        raise ValidationError("Il rapportino è già stato rimandato al collaboratore.")
    dimentica(CHIAVE_BADGE)
    return entry


def spese_da_rimborsare():
    """Spese pagate dai collaboratori, su rapportini confermati, non ancora rimborsate."""
    return CollaboratorExpense.objects.filter(
        paid_by=CollaboratorExpense.PAID_BY_COLLABORATOR,
        reimbursed_at__isnull=True,
        entry__status=CollaboratorTimeEntry.STATUS_APPROVED,
    ).select_related("entry", "entry__collaborator", "entry__job", "receipt")


def segna_rimborsate(id_spese, user):
    """Segna come rimborsate le spese indicate (solo quelle ancora da rimborsare).

    Si passano gli id mostrati in pagina, non «tutte»: una spesa confermata
    dopo che la pagina è stata aperta non viene rimborsata senza che la si veda.
    Restituisce quante spese sono state segnate.
    """
    id_spese = [int(valore) for valore in id_spese if str(valore).isdigit()]
    if not id_spese:
        return 0
    return spese_da_rimborsare().filter(pk__in=id_spese).update(reimbursed_at=timezone.now(), reimbursed_by=user)


def rapportini_da_confermare():
    """Quanti rapportini aspettano l'ufficio (per il pallino nel menu)."""
    return memoizza(
        CHIAVE_BADGE,
        lambda: CollaboratorTimeEntry.objects.filter(status=CollaboratorTimeEntry.STATUS_SUBMITTED).count(),
        60,
    )


def costi_collaboratori_cantiere(job):
    """Costi del cantiere che arrivano dai rapportini dei collaboratori.

    Contano solo i rapportini confermati: ore per collaboratore (con il costo,
    se ha un compenso orario) e spese per tipo. Quelli in attesa vengono
    solo contati, così si sa che il totale potrebbe crescere.
    """
    confermati = CollaboratorTimeEntry.objects.filter(job=job, status=CollaboratorTimeEntry.STATUS_APPROVED)

    manodopera = []
    totale_ore = ZERO
    costo_manodopera = ZERO
    senza_tariffa = False
    per_collaboratore = (
        confermati.values("collaborator_id", "collaborator__name", "collaborator__hourly_rate")
        .annotate(ore=Sum("hours"), giornate=Count("pk"))
        .order_by("collaborator__name")
    )
    for riga in per_collaboratore:
        ore = riga["ore"] or ZERO
        tariffa = riga["collaborator__hourly_rate"]
        costo = round2(ore * tariffa) if tariffa is not None else None
        if costo is None:
            senza_tariffa = True
        else:
            costo_manodopera += costo
        totale_ore += ore
        manodopera.append(
            {
                "collaboratore": riga["collaborator__name"],
                "collaboratore_id": riga["collaborator_id"],
                "ore": ore,
                "giornate": riga["giornate"],
                "tariffa": tariffa,
                "costo": costo,
            }
        )

    etichette = dict(CollaboratorExpense.CATEGORY_CHOICES)
    spese = OrderedDict()
    totale_spese = ZERO
    for riga in (
        CollaboratorExpense.objects.filter(entry__in=confermati)
        .values("category")
        .annotate(totale=Sum("amount"), quante=Count("pk"))
        .order_by("-totale")
    ):
        importo = round2(riga["totale"] or ZERO)
        spese[riga["category"]] = {"etichetta": etichette.get(riga["category"], riga["category"]), "totale": importo, "quante": riga["quante"]}
        totale_spese += importo

    return {
        "manodopera": manodopera,
        "ore": totale_ore,
        "costo_manodopera": round2(costo_manodopera),
        "senza_tariffa": senza_tariffa,
        "spese": list(spese.values()),
        "totale_spese": round2(totale_spese),
        "totale": round2(costo_manodopera + totale_spese),
        "in_attesa": CollaboratorTimeEntry.objects.filter(
            job=job, status=CollaboratorTimeEntry.STATUS_SUBMITTED
        ).count(),
        "vuoto": not manodopera and not spese,
    }

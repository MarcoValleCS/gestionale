"""Galleria fotografica: elenco con filtri per etichetta, caricamento e scheda."""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView

from apps.accounts.permissions import (
    ROLE_ADMIN,
    ROLE_HR,
    ROLE_PURCHASING,
    ROLE_SALES,
    ROLE_WAREHOUSE,
    RoleRequiredMixin,
    has_role,
    role_required,
)

from .forms import GalleryPhotoForm, GalleryUploadForm
from .models import GalleryPhoto, GalleryTag

GALLERY_ROLES = (ROLE_ADMIN, ROLE_SALES)
GALLERY_VIEW_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING, ROLE_WAREHOUSE, ROLE_HR)


def _etichette_inserite(testo):
    """Etichette scritte a mano («piscina grigia, scala ad angolo»)."""
    if not testo:
        return []
    pezzi = [parte.strip() for parte in testo.replace(";", ",").replace("\n", ",").split(",")]
    etichette = []
    for nome in pezzi:
        if not nome:
            continue
        etichetta = GalleryTag.objects.filter(name__iexact=nome).first()
        if etichetta is None:
            etichetta = GalleryTag.objects.create(name=nome[:60])
        etichette.append(etichetta)
    return etichette


def _applica_etichette(foto, tags, nuovo_testo):
    for etichetta in _etichette_inserite(nuovo_testo):
        foto.tags.add(etichetta)
    if tags:
        foto.tags.add(*tags)


class PhotoListView(RoleRequiredMixin, ListView):
    allowed_roles = GALLERY_VIEW_ROLES
    model = GalleryPhoto
    template_name = "gallery/photo_list.html"
    context_object_name = "photos"
    paginate_by = 24

    def get_queryset(self):
        foto = GalleryPhoto.objects.prefetch_related("tags").select_related("uploaded_by", "job")
        gestione = has_role(self.request.user, *GALLERY_ROLES)
        if not (gestione and self.request.GET.get("nascoste") == "1"):
            foto = foto.filter(active=True)
        for tag_id in self.request.GET.getlist("tag"):
            if tag_id.isdigit():
                foto = foto.filter(tags__id=int(tag_id))
        ricerca = self.request.GET.get("q", "").strip()
        if ricerca:
            foto = foto.filter(Q(title__icontains=ricerca) | Q(description__icontains=ricerca))
        cantiere = self.request.GET.get("cantiere", "")
        if cantiere.isdigit():
            foto = foto.filter(job_id=int(cantiere))
        return foto.distinct()

    def get_context_data(self, **kwargs):
        from apps.jobs.models import Job

        context = super().get_context_data(**kwargs)
        selezionati = [int(tid) for tid in self.request.GET.getlist("tag") if tid.isdigit()]
        context.update(
            {
                "page_title": "Galleria",
                "tags": GalleryTag.objects.annotate(quante=Count("photos")).order_by("name"),
                "tags_selezionati": selezionati,
                "search": self.request.GET.get("q", ""),
                "cantiere_id": self.request.GET.get("cantiere", ""),
                "nascoste": self.request.GET.get("nascoste") == "1",
                "jobs": Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name"),
                "puo_gestire": has_role(self.request.user, *GALLERY_ROLES),
            }
        )
        return context


@role_required(*GALLERY_ROLES)
def photo_create(request):
    """Carica una o più foto con le stesse etichette."""
    if request.method == "POST":
        form = GalleryUploadForm(request.POST, request.FILES)
        file_caricati = request.FILES.getlist("images")
        if not file_caricati:
            form.add_error("images", "Scegli almeno una foto.")
        elif form.is_valid():
            dati = form.cleaned_data
            for indice, file in enumerate(dati["images"]):
                titolo = dati.get("title") or ""
                if len(file_caricati) > 1 and titolo:
                    titolo = f"{titolo} ({indice + 1})"
                foto = GalleryPhoto.objects.create(
                    title=titolo[:150],
                    description=dati.get("description") or "",
                    image=file,
                    job=dati.get("job"),
                    active=dati.get("active"),
                    uploaded_by=request.user,
                )
                _applica_etichette(foto, dati.get("tags"), dati.get("new_tags"))
            messages.success(request, f"Caricate {len(file_caricati)} foto in galleria.")
            return redirect("gallery:photo_list")
    else:
        form = GalleryUploadForm()
    return render(
        request,
        "gallery/photo_form.html",
        {"page_title": "Carica foto", "form": form, "cancel_url": reverse("gallery:photo_list")},
    )


@role_required(*GALLERY_VIEW_ROLES)
def photo_detail(request, pk):
    foto = get_object_or_404(GalleryPhoto.objects.prefetch_related("tags").select_related("uploaded_by", "job"), pk=pk)
    if not foto.active and not has_role(request.user, *GALLERY_ROLES):
        messages.warning(request, "Questa foto non è visibile in galleria.")
        return redirect("gallery:photo_list")
    return render(
        request,
        "gallery/photo_detail.html",
        {
            "page_title": foto.title or "Foto",
            "foto": foto,
            "puo_gestire": has_role(request.user, *GALLERY_ROLES),
        },
    )


@role_required(*GALLERY_ROLES)
def photo_update(request, pk):
    foto = get_object_or_404(GalleryPhoto, pk=pk)
    if request.method == "POST":
        form = GalleryPhotoForm(request.POST, request.FILES, instance=foto)
        if form.is_valid():
            foto = form.save()
            _applica_etichette(foto, form.cleaned_data.get("tags"), form.cleaned_data.get("new_tags"))
            messages.success(request, "Foto aggiornata.")
            return redirect("gallery:photo_detail", pk=foto.pk)
    else:
        form = GalleryPhotoForm(instance=foto, initial={"tags": foto.tags.all()})
    return render(
        request,
        "gallery/photo_form.html",
        {
            "page_title": f"Modifica foto: {foto}",
            "form": form,
            "foto": foto,
            "cancel_url": reverse("gallery:photo_detail", args=[foto.pk]),
        },
    )


@role_required(*GALLERY_ROLES)
def photo_delete(request, pk):
    foto = get_object_or_404(GalleryPhoto, pk=pk)
    if request.method == "POST":
        titolo = str(foto)
        foto.image.delete(save=False)
        foto.delete()
        messages.success(request, f"Foto «{titolo}» eliminata.")
    return redirect("gallery:photo_list")

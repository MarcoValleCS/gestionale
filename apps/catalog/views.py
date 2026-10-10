from decimal import Decimal
import re

from django.contrib import messages
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, RoleRequiredMixin, role_required
from apps.contacts.models import Contact
from apps.core.models import Tag
from apps.core.utils import format_money, to_decimal
from apps.inventory.models import StockLevel

from . import importer
from .forms import CategoryForm, ProductForm, ProductImportForm, ProductQuickForm
from .models import Category, KitComponent, Product

# Somma delle giacenze come sottoquery correlata, non come JOIN + GROUP BY:
# con il raggruppamento il database doveva materializzare tutto il catalogo
# (due B-tree temporanei) a ogni apertura della lista articoli, e l'indice su
# (active, name) non poteva più essere usato per l'ordinamento.
STOCK_SUM = Coalesce(
    Subquery(
        StockLevel.objects.filter(product=OuterRef("pk"))
        .values("product")
        .annotate(total=Sum("quantity"))
        .values("total"),
        output_field=DecimalField(max_digits=14, decimal_places=3),
    ),
    Value(0),
    output_field=DecimalField(max_digits=14, decimal_places=3),
)

EDIT_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING)


class ProductListView(ListView):
    model = Product
    template_name = "catalog/product_list.html"
    context_object_name = "products"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("uom", "category", "main_supplier")
            .prefetch_related("tags")
            .annotate(stock_total=STOCK_SUM)
            .order_by("name")
        )
        search = self.request.GET.get("q", "").strip()
        if search:
            from apps.catalog.search import filtro_articoli

            queryset = queryset.filter(filtro_articoli(search))
        category_id = self.request.GET.get("categoria", "")
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        # Il filtro per etichetta passa dalla relazione molti-a-molti e può
        # ripetere la stessa riga: solo in questo caso serve DISTINCT.
        # Applicarlo sempre costava una deduplicazione su tutto il catalogo.
        needs_distinct = False
        tag_id = self.request.GET.get("tag", "")
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
            needs_distinct = True
        supplier_id = self.request.GET.get("fornitore", "")
        if supplier_id:
            queryset = queryset.filter(main_supplier_id=supplier_id)
        if self.request.GET.get("sotto_scorta") == "1":
            queryset = queryset.filter(is_stock_tracked=True, min_stock__gt=0, stock_total__lt=F("min_stock"))
        if self.request.GET.get("principali") == "1":
            queryset = queryset.filter(parent__isnull=True)
        if self.request.GET.get("inattivi") != "1":
            queryset = queryset.filter(active=True)
        return queryset.distinct() if needs_distinct else queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Articoli"
        context["categories"] = Category.objects.all()
        context["tags"] = Tag.objects.all()
        context["suppliers"] = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        context["search"] = self.request.GET.get("q", "")
        context["category_id"] = self.request.GET.get("categoria", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["supplier_id"] = self.request.GET.get("fornitore", "")
        context["low_stock_only"] = self.request.GET.get("sotto_scorta") == "1"
        context["main_only"] = self.request.GET.get("principali") == "1"
        context["show_inactive"] = self.request.GET.get("inattivi") == "1"
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = "catalog/product_detail.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        context["page_title"] = product.name
        context["stock_levels"] = product.stock_levels.select_related("warehouse").order_by("warehouse__name")
        context["movements"] = product.movements.select_related("warehouse", "created_by").order_by("-created_at")[:25]
        context["price_list_items"] = (
            product.price_list_items.select_related("pricelist", "pricelist__supplier").order_by("pricelist__supplier__name")
        )
        context["variants"] = product.variants.order_by("name")
        context["components"] = product.components.select_related("component").order_by("component__name")
        context["attachments"] = product.attachments.select_related("uploaded_by")[:20]
        return context


class ProductCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = EDIT_ROLES
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"

    def get_success_url(self):
        return reverse_lazy("catalog:product_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo articolo"
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Articolo «{form.instance.name}» creato.")
        return super().form_valid(form)


class ProductUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = EDIT_ROLES
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"

    def get_success_url(self):
        return reverse_lazy("catalog:product_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica: {self.object.name}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Articolo aggiornato.")
        return super().form_valid(form)


def product_defaults(request, pk):
    """Dati per il riempimento automatico delle righe documento (JSON)."""
    product = get_object_or_404(Product, pk=pk)
    context_type = request.GET.get("context", "sale")
    supplier_id = request.GET.get("supplier")
    supplier = Contact.objects.filter(pk=supplier_id).first() if supplier_id else product.main_supplier

    if context_type == "purchase":
        vat = product.purchase_vat
        price = product.purchase_unit_price(supplier)
    else:
        vat = product.sale_vat
        price = product.sale_price

    components = []
    if product.is_kit:
        for item in product.components.select_related("component").order_by("component__name"):
            components.append(
                {
                    "id": item.component_id,
                    "label": f"{item.component.code} – {item.component.name}",
                    "qty": f"{item.qty:f}".rstrip("0").rstrip(".") or "1",
                    "description": f"{item.component.name} (componente {product.code})",
                }
            )

    return JsonResponse(
        {
            "code": product.code,
            "name": product.name,
            "description": product.description or product.name,
            "uom_id": product.uom_id,
            "uom_label": str(product.uom),
            "vat_id": vat.pk if vat else "",
            "vat_label": str(vat) if vat else "",
            "price": str(price or Decimal("0")),
            "cost": str(product.purchase_price or Decimal("0")),
            "supplier_id": supplier.id if supplier else "",
            "is_kit": product.is_kit,
            "components": components,
        }
    )


@role_required(*EDIT_ROLES)
def product_variants_create(request, pk):
    """Genera le varianti (colore/finitura) di un articolo, tanti SKU quante sono le varianti."""
    product = get_object_or_404(Product, pk=pk)
    if request.method != "POST":
        return redirect("catalog:product_detail", pk=product.pk)

    values = [value.strip() for value in re.split(r"[,;\n]+", request.POST.get("values", "")) if value.strip()]
    if not values:
        messages.warning(request, "Indica almeno una variante (es. Bianco, Nero).")
        return redirect("catalog:product_detail", pk=product.pk)

    created = 0
    for value in values:
        label = value[:60]
        exists = product.variants.filter(variant_label__iexact=label).exists()
        if exists:
            continue
        Product.objects.create(
            name=f"{product.name} – {label}",
            description=product.description,
            category=product.category,
            uom=product.uom,
            sale_price=product.sale_price,
            sale_vat=product.sale_vat,
            purchase_price=product.purchase_price,
            purchase_vat=product.purchase_vat,
            main_supplier=product.main_supplier,
            supplier_lead_days=product.supplier_lead_days,
            is_stock_tracked=product.is_stock_tracked,
            min_stock=product.min_stock,
            parent=product,
            variant_label=label,
        )
        created += 1

    if created:
        messages.success(request, f"Create {created} varianti di «{product.name}». Ogni variante è un articolo a sé: impostane giacenza e prezzi.")
    else:
        messages.info(request, "Nessuna nuova variante creata (esistevano già).")
    return redirect("catalog:product_detail", pk=product.pk)


@role_required(*EDIT_ROLES)
def product_component_add(request, pk):
    """Aggiunge (o aggiorna) un componente del kit."""
    kit = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        component = Product.objects.filter(pk=request.POST.get("component")).first()
        qty = to_decimal(request.POST.get("qty"), Decimal("1"))
        if component is None:
            messages.error(request, "Scegli un componente valido.")
        elif component.pk == kit.pk:
            messages.error(request, "Un kit non può contenere se stesso.")
        else:
            item, created = KitComponent.objects.get_or_create(kit=kit, component=component, defaults={"qty": qty})
            if not created and item.qty != qty:
                item.qty = qty
                item.save(update_fields=["qty"])
            messages.success(request, f"Componente «{component.name}» {'aggiunto al' if created else 'aggiornato nel'} kit.")
    return redirect("catalog:product_detail", pk=kit.pk)


@role_required(*EDIT_ROLES)
def product_component_remove(request, pk):
    kit = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        removed, _ = KitComponent.objects.filter(kit=kit, component_id=request.POST.get("component")).delete()
        if removed:
            messages.success(request, "Componente rimosso dal kit.")
    return redirect("catalog:product_detail", pk=kit.pk)


@role_required(*EDIT_ROLES)
def product_quick_create(request):
    """Creazione rapida di un articolo dai documenti (risposta JSON)."""
    if request.method != "POST":
        return JsonResponse({"error": "Metodo non consentito."}, status=405)

    context_type = request.POST.get("context", "sale")
    form = ProductQuickForm(request.POST, context_type=context_type)
    if form.is_valid():
        product = form.save()
        return JsonResponse({"id": product.pk, "label": f"{product.code} – {product.name}", "code": product.code})

    errors = {field: [entry["message"] for entry in entries] for field, entries in form.errors.get_json_data().items()}
    return JsonResponse({"errors": errors}, status=400)


@role_required(*EDIT_ROLES)
def product_search(request):
    """Ricerca articoli per l'autocompletamento nelle righe documento (JSON)."""
    query = request.GET.get("q", "").strip()
    context_type = request.GET.get("context", "sale")
    queryset = Product.objects.filter(active=True).select_related("uom")
    if query:
        from apps.catalog.search import filtro_articoli

        queryset = queryset.filter(filtro_articoli(query))

    results = []
    for product in queryset.order_by("name")[:12]:
        price = product.purchase_price if context_type == "purchase" else product.sale_price
        extra_parts = [f"{format_money(price)} €"]
        if product.category_id:
            extra_parts.append(product.category.name)
        extra_parts.append(product.uom.code)
        results.append(
            {
                "id": product.pk,
                "label": f"{product.code} – {product.name}",
                "extra": " · ".join(extra_parts),
            }
        )
    return JsonResponse({"results": results})


@role_required(*EDIT_ROLES)
def product_import(request):
    """Importazione articoli da CSV/Excel."""
    report = None
    if request.method == "POST":
        form = ProductImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                rows = importer.read_table(form.cleaned_data["file"])
                report = importer.import_products(
                    rows,
                    default_supplier=form.cleaned_data.get("supplier"),
                    update_pricelist=form.cleaned_data.get("update_pricelist"),
                    user=request.user,
                )
                if report.processed:
                    messages.success(
                        request,
                        f"Importazione completata: {report.created} articoli creati, {report.updated} aggiornati.",
                    )
                if report.price_items:
                    messages.info(request, f"Aggiornate {report.price_items} voci di listino fornitore.")
                if report.errors:
                    messages.error(request, f"{len(report.errors)} righe non importate: dettaglio qui sotto.")
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = ProductImportForm()

    return render(
        request,
        "catalog/product_import.html",
        {
            "form": form,
            "report": report,
            "columns": importer.COLUMN_DOCS,
            "page_title": "Importa articoli da CSV/Excel",
        },
    )


@role_required(*EDIT_ROLES)
def product_import_template(request):
    response = HttpResponse(importer.build_template_csv(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="modello_import_articoli.csv"'
    return response


# --------------------------------------------------------------- Categorie
class CategoryListView(RoleRequiredMixin, ListView):
    allowed_roles = EDIT_ROLES
    model = Category
    template_name = "catalog/category_list.html"
    context_object_name = "categories"
    paginate_by = 50

    def get_queryset(self):
        return Category.objects.select_related("parent").annotate(product_count=Sum("products")).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Categorie articoli"
        return context


class CategoryCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = EDIT_ROLES
    model = Category
    form_class = CategoryForm
    template_name = "catalog/category_form.html"
    success_url = reverse_lazy("catalog:category_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova categoria"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Categoria creata.")
        return super().form_valid(form)


class CategoryUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = EDIT_ROLES
    model = Category
    form_class = CategoryForm
    template_name = "catalog/category_form.html"
    success_url = reverse_lazy("catalog:category_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica categoria: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Categoria aggiornata.")
        return super().form_valid(form)

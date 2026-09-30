from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import F, OuterRef, Q, Subquery, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_WAREHOUSE, role_required
from apps.catalog.models import Product

from .forms import AdjustForm
from .models import StockLevel, StockMovement, Warehouse
from .services import register_movement


class StockListView(ListView):
    model = StockLevel
    template_name = "inventory/stock_list.html"
    context_object_name = "levels"
    paginate_by = 50

    def get_queryset(self):
        totals = (
            StockLevel.objects.filter(product=OuterRef("product"))
            .values("product")
            .annotate(total=Sum("quantity"))
            .values("total")
        )
        queryset = (
            StockLevel.objects.select_related("product", "product__uom", "product__main_supplier", "warehouse")
            .annotate(product_total=Subquery(totals))
            .order_by("product__name")
        )
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(product__code__icontains=search))
        warehouse_id = self.request.GET.get("magazzino", "")
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if self.request.GET.get("sotto_scorta") == "1":
            queryset = queryset.filter(product__min_stock__gt=0, product_total__lt=F("product__min_stock"))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Giacenze"
        context["warehouses"] = Warehouse.objects.filter(active=True)
        context["search"] = self.request.GET.get("q", "")
        context["warehouse_id"] = self.request.GET.get("magazzino", "")
        context["low_stock_only"] = self.request.GET.get("sotto_scorta") == "1"
        context["can_adjust"] = self.request.user.is_superuser or self.request.user.groups.filter(name__in=[ROLE_ADMIN, ROLE_WAREHOUSE]).exists()
        return context


class MovementListView(ListView):
    model = StockMovement
    template_name = "inventory/movement_list.html"
    context_object_name = "movements"
    paginate_by = 50

    def get_queryset(self):
        queryset = StockMovement.objects.select_related("product", "warehouse", "created_by").order_by("-created_at", "-pk")
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(product__code__icontains=search) | Q(reference__icontains=search))
        movement_type = self.request.GET.get("tipo", "")
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        warehouse_id = self.request.GET.get("magazzino", "")
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        product_id = self.request.GET.get("articolo", "")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Movimenti di magazzino"
        context["warehouses"] = Warehouse.objects.filter(active=True)
        context["types"] = StockMovement.TYPE_CHOICES
        context["search"] = self.request.GET.get("q", "")
        context["movement_type"] = self.request.GET.get("tipo", "")
        context["warehouse_id"] = self.request.GET.get("magazzino", "")
        context["product_id"] = self.request.GET.get("articolo", "")
        return context


@role_required(ROLE_ADMIN, ROLE_WAREHOUSE)
def adjust_create(request):
    initial = {}
    product_id = request.GET.get("articolo")
    if product_id:
        initial["product"] = product_id
    warehouse_id = request.GET.get("magazzino")
    if warehouse_id:
        initial["warehouse"] = warehouse_id

    form = AdjustForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        product = form.cleaned_data["product"]
        warehouse = form.cleaned_data["warehouse"]
        new_quantity = form.cleaned_data["new_quantity"]
        note = form.cleaned_data["note"]

        current = StockLevel.objects.filter(product=product, warehouse=warehouse).first()
        current_qty = current.quantity if current else 0
        delta = new_quantity - current_qty
        if delta == 0:
            messages.info(request, "La giacenza è già uguale al valore inserito: nessun movimento registrato.")
        else:
            register_movement(
                product=product,
                warehouse=warehouse,
                delta=delta,
                movement_type=StockMovement.TYPE_ADJUST,
                user=request.user,
                note=note,
            )
            messages.success(request, f"Rettifica registrata: {product.name} ora ha giacenza {new_quantity} in {warehouse.name}.")
        return redirect("inventory:stock_list")

    return render(request, "inventory/adjust_form.html", {"form": form, "page_title": "Rettifica giacenza"})


def stock_info(request, pk):
    """Giacenza attuale di un articolo (JSON) per il form di rettifica."""
    product = get_object_or_404(Product, pk=pk)
    warehouse_id = request.GET.get("magazzino")
    warehouse = Warehouse.objects.filter(pk=warehouse_id).first() if warehouse_id else Warehouse.get_default()
    level = StockLevel.objects.filter(product=product, warehouse=warehouse).first() if warehouse else None
    return JsonResponse(
        {
            "current": str(level.quantity if level else 0),
            "uom": product.uom.code,
            "warehouse": str(warehouse) if warehouse else "",
        }
    )

"""Servizi di magazzino: unico punto di modifica delle giacenze."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .models import StockLevel, StockMovement, Warehouse


@transaction.atomic
def register_movement(
    *,
    product,
    warehouse=None,
    delta,
    movement_type,
    user=None,
    note="",
    reference="",
    unit_cost=None,
    allow_negative=False,
):
    """Registra un movimento di magazzino aggiornando la giacenza.

    Solleva ``ValidationError`` se lo scarico renderebbe la giacenza negativa
    (a meno di ``allow_negative=True``).
    """
    if warehouse is None:
        warehouse = Warehouse.get_default()
    if warehouse is None:
        raise ValidationError("Nessun magazzino configurato.")

    delta = Decimal(delta)
    if delta == 0:
        return None

    level, _created = StockLevel.objects.get_or_create(product=product, warehouse=warehouse)

    # L'incremento avviene con un UPDATE atomico a livello di database, non con
    # una lettura seguita da una scrittura: così due scarichi contemporanei dello
    # stesso articolo non possono leggere la stessa giacenza e sovrascriversi.
    # Serve perché ``select_for_update`` non ha effetto su SQLite (che non
    # supporta il blocco di riga): l'UPDATE prende comunque il blocco di
    # scrittura e mette in coda l'altra transazione.
    StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + delta)
    level.refresh_from_db(fields=["quantity"])

    available = level.quantity - delta  # giacenza com'era prima del movimento
    if level.quantity < 0 and not allow_negative:
        raise ValidationError(
            f"Giacenza insufficiente di «{product.name}»: disponibili {available}, richiesti {abs(delta)}."
        )

    return StockMovement.objects.create(
        product=product,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=delta,
        unit_cost=unit_cost,
        reference=reference,
        note=note,
        created_by=user,
    )


def current_stock(product, warehouse=None):
    if warehouse is None:
        return product.total_stock
    level = StockLevel.objects.filter(product=product, warehouse=warehouse).first()
    return level.quantity if level else Decimal("0")

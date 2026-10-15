"""Demo data: users, catalog and ~45 days of realistic movements.

Every movement goes through stock_service.apply_movement, the same function the app uses,
so the demo ledger obeys every rule (no negative stock, chronological, kardex adds up).
The simulation is deterministic (fixed random seed): the same command always builds the
same shop, which makes screenshots and demos reproducible.
"""
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy import delete, func, select

from app.demo import DEMO_ACCOUNTS
from app.extensions import db
from app.models import Category, MovementReason, MovementType, Product, StockMovement, Supplier, User, UserRole
from app.services.exceptions import BusinessRuleError
from app.services.stock_service import apply_movement
from app.utils.dates import local_to_utc, local_today, to_local, utc_now
from app.utils.peru import ruc_check_digit


def _ruc(first_ten: str) -> str:
    return first_ten + str(ruc_check_digit(first_ten))


CATEGORIES = [
    ("Abarrotes", "Arroz, azúcar, aceite, fideos y conservas"),
    ("Bebidas", "Gaseosas, agua y jugos"),
    ("Lácteos", "Leche, yogur y quesos"),
    ("Limpieza", "Detergentes, lejía y artículos de limpieza"),
    ("Cuidado personal", "Jabón, champú y papel higiénico"),
    ("Snacks y golosinas", "Galletas, chocolates y piqueos"),
    ("Ferretería", "Herramientas, clavos y pinturas"),
    ("Electricidad", "Cables, focos y accesorios eléctricos"),
]

# key: (name, RUC or None, contact, phone, email, active)
SUPPLIERS = {
    "norte": ("Distribuidora Alimenticia del Norte S.A.C.", _ruc("2060123456"), "Rosa Quispe", "(01) 528-4410", "ventas@danorte.pe", True),
    "andinos": ("Lácteos Andinos S.A.", _ruc("2051234567"), "Carlos Huamán", "987 654 321", "pedidos@lacteosandinos.pe", True),
    "limpiamax": ("Comercial Limpiamax S.A.C.", _ruc("2060987654"), "Lucía Torres", "(01) 445-9087", None, True),
    "ferreind": ("Ferretería Industrial Lima E.I.R.L.", _ruc("2054321098"), "Jorge Ramos", "956 112 334", "jramos@ferreind.pe", True),
    "bebidas": ("Bebidas del Sur S.A.C.", _ruc("2055667788"), None, "(054) 23-1188", None, True),
    "mayorista": ("Mercado Mayorista (compras al contado)", None, None, None, None, True),
    "antiguo": ("Importadora Rímac S.R.L.", _ruc("2049876543"), None, None, None, False),
}


@dataclass(frozen=True)
class DemoProduct:
    sku: str
    name: str
    category: str
    supplier: str | None
    unit: str
    purchase: str
    sale: str
    min_stock: str
    demand: float  # average quantity sold per day


PRODUCTS = [
    DemoProduct("ARR-5KG", "Arroz extra 5 kg", "Abarrotes", "norte", "UND", "18.50", "22.90", "10", 2.2),
    DemoProduct("ARR-GRA", "Arroz a granel", "Abarrotes", "mayorista", "KG", "3.60", "4.50", "25", 7.0),
    DemoProduct("AZU-1KG", "Azúcar rubia 1 kg", "Abarrotes", "norte", "UND", "4.10", "5.20", "15", 3.0),
    DemoProduct("ACE-1L", "Aceite vegetal 1 L", "Abarrotes", "norte", "UND", "9.90", "11.50", "8", 1.8),
    DemoProduct("FID-500", "Fideos spaghetti 500 g", "Abarrotes", "norte", "UND", "2.80", "3.60", "20", 4.0),
    DemoProduct("ATU-170", "Atún en trozos 170 g", "Abarrotes", "norte", "UND", "5.20", "6.50", "12", 1.5),
    DemoProduct("LEN-500", "Lentejas 500 g", "Abarrotes", "mayorista", "UND", "4.50", "5.80", "10", 1.0),
    DemoProduct("GAS-500", "Gaseosa 500 ml", "Bebidas", "bebidas", "UND", "1.70", "2.50", "24", 6.0),
    DemoProduct("GAS-3L", "Gaseosa 3 L", "Bebidas", "bebidas", "UND", "8.20", "10.50", "10", 1.6),
    DemoProduct("AGU-625", "Agua mineral sin gas 625 ml", "Bebidas", "bebidas", "UND", "1.10", "1.80", "24", 5.0),
    DemoProduct("JUG-1L", "Jugo de naranja 1 L", "Bebidas", "bebidas", "UND", "4.30", "5.50", "6", 0.8),
    DemoProduct("LEC-400", "Leche evaporada 400 g", "Lácteos", "andinos", "UND", "3.20", "3.80", "24", 6.0),
    DemoProduct("YOG-1L", "Yogur de fresa 1 L", "Lácteos", "andinos", "UND", "6.10", "7.50", "8", 1.2),
    DemoProduct("QUE-FRE", "Queso fresco", "Lácteos", "andinos", "KG", "22.00", "28.00", "3", 0.9),
    DemoProduct("MAN-200", "Mantequilla 200 g", "Lácteos", "andinos", "UND", "7.40", "9.20", "6", 0.6),
    DemoProduct("DET-1KG", "Detergente en polvo 1 kg", "Limpieza", "limpiamax", "UND", "12.40", "15.90", "8", 0.9),
    DemoProduct("LEJ-1L", "Lejía 1 L", "Limpieza", "limpiamax", "UND", "2.60", "3.50", "10", 1.1),
    DemoProduct("LAV-500", "Lavavajillas en pasta 500 g", "Limpieza", "limpiamax", "UND", "3.90", "5.00", "8", 0.8),
    DemoProduct("PAP-4R", "Papel higiénico x4 rollos", "Cuidado personal", "limpiamax", "PAQ", "5.60", "7.20", "12", 2.0),
    DemoProduct("JAB-3U", "Jabón de tocador x3", "Cuidado personal", "limpiamax", "PAQ", "6.30", "8.00", "6", 0.7),
    DemoProduct("CHA-400", "Champú 400 ml", "Cuidado personal", None, "UND", "11.80", "14.90", "4", 0.4),
    DemoProduct("GAL-SOD", "Galletas de soda x6", "Snacks y golosinas", "norte", "PAQ", "2.90", "3.80", "15", 3.0),
    DemoProduct("CHO-30G", "Chocolate de leche 30 g", "Snacks y golosinas", "norte", "UND", "0.90", "1.50", "30", 6.0),
    DemoProduct("PAP-FRI", "Papas fritas 150 g", "Snacks y golosinas", None, "UND", "3.10", "4.50", "10", 1.5),
    DemoProduct("MAR-16", "Martillo de uña 16 oz", "Ferretería", "ferreind", "UND", "24.00", "35.00", "3", 0.15),
    DemoProduct("CLA-2P", "Clavos de 2 pulgadas", "Ferretería", "ferreind", "KG", "6.50", "9.00", "5", 0.8),
    DemoProduct("PIN-GAL", "Pintura látex blanca 1 gal", "Ferretería", "ferreind", "UND", "32.00", "42.00", "4", 0.3),
    DemoProduct("WIN-CIN", "Cinta aislante 20 m", "Electricidad", "ferreind", "UND", "2.40", "3.50", "10", 0.8),
    DemoProduct("CAB-14", "Cable mellizo N.º 14", "Electricidad", "ferreind", "M", "2.30", "3.50", "50", 9.0),
    DemoProduct("FOC-9W", "Foco LED 9 W luz blanca", "Electricidad", "ferreind", "UND", "4.80", "7.00", "12", 1.2),
]

# Products whose restocking "was forgotten" in the last days. A big sale on the last evening
# leaves them at this fraction of their minimum, so the demo ALWAYS shows alerts
# (0 = out of stock). Deterministic on purpose: random sales alone wouldn't guarantee it.
ENDING_LEVELS = {"ACE-1L": "0", "AZU-1KG": "0.4", "FOC-9W": "0.5", "QUE-FRE": "0.5"}
NO_RESTOCK_LAST_DAYS = 5
DISCONTINUED = {"JUG-1L"}  # ends inactive (soft-deleted), with its history kept

SHRINKAGE_CATEGORIES = {"Lácteos"}  # perishables occasionally expire


def has_data() -> bool:
    users = db.session.execute(select(func.count(User.id))).scalar_one()
    products = db.session.execute(select(func.count(Product.id))).scalar_one()
    return bool(users or products)


def clear_all_data() -> None:
    """Delete everything, children first (the foreign keys are RESTRICT)."""
    for model in (StockMovement, Product, Supplier, Category, User):
        db.session.execute(delete(model))
    db.session.commit()


def seed_demo_data(days: int = 45, seed: int = 2026) -> dict:
    """Create the demo shop. Expects an empty database (see has_data / clear_all_data)."""
    rng = random.Random(seed)
    tz = current_app.config["APP_TIMEZONE"]
    today = local_today(tz)
    first_day = today - timedelta(days=days)

    users = {}
    for username, full_name, role, password in DEMO_ACCOUNTS:
        user = User(username=username, full_name=full_name, role=role)
        user.set_password(password)
        users[role] = user
        db.session.add(user)
    admin, employee = users[UserRole.ADMIN], users[UserRole.EMPLOYEE]

    categories = {name: Category(name=name, description=desc) for name, desc in CATEGORIES}
    suppliers = {
        key: Supplier(name=n, ruc=ruc, contact_name=contact, phone=phone, email=email, is_active=active)
        for key, (n, ruc, contact, phone, email, active) in SUPPLIERS.items()
    }
    db.session.add_all([*categories.values(), *suppliers.values()])

    products: dict[str, tuple[Product, DemoProduct]] = {}
    for spec in PRODUCTS:
        product = Product(
            sku=spec.sku, name=spec.name, category=categories[spec.category],
            supplier=suppliers[spec.supplier] if spec.supplier else None, unit=spec.unit,
            purchase_price=Decimal(spec.purchase), sale_price=Decimal(spec.sale),
            min_stock=Decimal(spec.min_stock), stock=Decimal("0"),
        )
        db.session.add(product)
        products[spec.sku] = (product, spec)
    db.session.flush()

    counters = {"invoice": 120, "movements": 0}

    def at(day: date, hour: int, minute: int) -> datetime:
        return local_to_utc(day, time(hour, minute), tz)

    def record(product, movement_type, reason, quantity, user, when, notes=None) -> None:
        try:
            apply_movement(product, movement_type=movement_type, reason=reason, quantity=quantity,
                           user=user, movement_date=when, notes=notes)
            counters["movements"] += 1
        except BusinessRuleError:
            pass  # e.g. a sale larger than the stock left: a real shop simply can't sell it

    # Day 0: opening inventory, recorded as an adjustment (same convention as product creation).
    for product, spec in products.values():
        opening = _qty(spec, max(float(spec.min_stock) * 2.5, spec.demand * 12))
        record(product, MovementType.IN, MovementReason.ADJUSTMENT, opening, admin,
               at(first_day, 8, 0), "Inventario inicial")
    db.session.commit()

    # Full days from the day after the opening up to yesterday (today is handled below,
    # because random hours later than "now" would be movements in the future).
    for offset in range(1, days):
        day = first_day + timedelta(days=offset)
        days_left = (today - day).days - 1  # full days remaining before today
        events = []
        for product, spec in products.values():
            if spec.sku in DISCONTINUED and offset > days * 0.6:
                continue  # no longer sold or bought
            # Restock in the morning when stock is near the minimum (unless it was "forgotten").
            forgotten = spec.sku in ENDING_LEVELS and days_left < NO_RESTOCK_LAST_DAYS
            if not forgotten and product.stock <= product.min_stock * Decimal("1.3"):
                quantity = _qty(spec, max(float(product.min_stock) * 3, spec.demand * 10))
                counters["invoice"] += 1
                events.append((at(day, 9, rng.randint(0, 50)), product, MovementType.IN, MovementReason.PURCHASE,
                               quantity, admin, f"Factura F001-{counters['invoice']:06d}"))
            # Sales spread over the day.
            for _ in range(_sales_count(rng, spec.demand)):
                quantity = _sale_qty(rng, spec)
                seller = employee if rng.random() < 0.75 else admin
                events.append((at(day, rng.randint(10, 20), rng.randint(0, 59)), product, MovementType.OUT,
                               MovementReason.SALE, quantity, seller, None))
            # Occasional shrinkage and customer returns.
            if spec.category in SHRINKAGE_CATEGORIES and rng.random() < 0.06:
                events.append((at(day, 21, 0), product, MovementType.OUT, MovementReason.SHRINKAGE,
                               _qty(spec, 1), admin, "Producto vencido"))
            if rng.random() < 0.01:
                events.append((at(day, 18, rng.randint(0, 59)), product, MovementType.IN,
                               MovementReason.CUSTOMER_RETURN, _qty(spec, 1), employee, "Cliente devolvió producto cerrado"))
        if days_left == 0:  # last full day: the large closing sales described in ENDING_LEVELS
            for sku, fraction in ENDING_LEVELS.items():
                product, spec = products[sku]
                target = _floor_qty(spec, product.min_stock * Decimal(fraction))
                events.append((at(day, 20, 58), product, MovementType.OUT, MovementReason.SALE,
                               product.stock - target, employee, "Venta por mayor"))
        for when, product, movement_type, reason, quantity, user, notes in sorted(events, key=lambda e: e[0]):
            if movement_type == MovementType.OUT and notes == "Venta por mayor":
                # Recompute with the stock left after the day's earlier sales.
                target = _floor_qty(products[product.sku][1], product.min_stock * Decimal(ENDING_LEVELS[product.sku]))
                quantity = product.stock - target
                if quantity <= 0:
                    continue
            record(product, movement_type, reason, quantity, user, when, notes)
        db.session.commit()

    # A few sales already today (only if they are not in the future, so new movements stay valid).
    now = utc_now()
    for minutes_ago, sku in ((150, "LEC-400"), (95, "GAS-500"), (40, "ARR-5KG")):
        when = now - timedelta(minutes=minutes_ago)
        if to_local(when, tz).date() == today:
            product, spec = products[sku]
            record(product, MovementType.OUT, MovementReason.SALE, _qty(spec, 2), employee, when)
    for sku in DISCONTINUED:
        products[sku][0].is_active = False
    db.session.commit()

    active = [p for p, _ in products.values() if p.is_active]
    return {
        "users": len(DEMO_ACCOUNTS),
        "categories": len(categories),
        "suppliers": len(suppliers),
        "products": len(products),
        "movements": counters["movements"],
        "low_stock": sum(1 for p in active if p.is_low_stock),
        "out_of_stock": sum(1 for p in active if p.is_out_of_stock),
    }


def _qty(spec: DemoProduct, value: float) -> Decimal:
    """Round to what the unit allows: whole numbers for UND/PAQ, quarters for KG/M."""
    if spec.unit in {"KG", "M"}:
        return max(Decimal(str(round(value * 4) / 4)), Decimal("0.25"))
    return Decimal(max(1, round(value)))


def _floor_qty(spec: DemoProduct, value: Decimal) -> Decimal:
    """Round DOWN to what the unit allows (quarters for KG/M, whole numbers otherwise)."""
    step = Decimal("0.25") if spec.unit in {"KG", "M"} else Decimal("1")
    return (value / step).to_integral_value(rounding="ROUND_FLOOR") * step


def _sales_count(rng: random.Random, demand: float) -> int:
    """How many separate sales happen in a day (low-demand items often sell nothing)."""
    if demand < 1:
        return 1 if rng.random() < demand else 0
    return rng.randint(1, max(1, round(demand)))


def _sale_qty(rng: random.Random, spec: DemoProduct) -> Decimal:
    if spec.unit == "KG":
        return Decimal(str(rng.choice([0.25, 0.5, 0.5, 1, 1, 1.5, 2])))
    if spec.unit == "M":
        return Decimal(rng.choice([1, 2, 3, 5, 5, 10]))
    return Decimal(rng.choice([1, 1, 1, 2, 2, 3]))

"""Jinja filters: values are stored in a technical format and shown in a Peruvian one."""
from datetime import datetime
from decimal import Decimal

from flask import current_app

from app.utils.dates import to_local


def local_datetime(value: datetime | None, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """Stored UTC datetime -> local time text, e.g. 15/10/2026 09:30."""
    local = to_local(value, current_app.config["APP_TIMEZONE"])
    return local.strftime(fmt) if local else "—"


def money(value: Decimal | float | None) -> str:
    """1234.5 -> 'S/ 1,234.50'."""
    if value is None:
        return "—"
    return f"{current_app.config['CURRENCY_SYMBOL']} {Decimal(value):,.2f}"


def quantity(value: Decimal | float | None) -> str:
    """Drop useless decimals: 10.000 -> '10', 2.500 -> '2.5'."""
    if value is None:
        return "—"
    text = f"{Decimal(value):,.3f}".rstrip("0").rstrip(".")
    return text or "0"

"""Import every model here so `from app import models` registers all tables."""
from app.models.category import Category
from app.models.product import FRACTIONAL_UNITS, UNITS, Product
from app.models.stock_movement import REASONS_BY_TYPE, MovementReason, MovementType, StockMovement
from app.models.supplier import Supplier
from app.models.user import User, UserRole

__all__ = [
    "Category",
    "FRACTIONAL_UNITS",
    "MovementReason",
    "MovementType",
    "Product",
    "REASONS_BY_TYPE",
    "StockMovement",
    "Supplier",
    "UNITS",
    "User",
    "UserRole",
]

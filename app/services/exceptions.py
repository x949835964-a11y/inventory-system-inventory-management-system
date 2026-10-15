"""Business exceptions raised by services. Their messages are safe to show to the user."""


class BusinessRuleError(Exception):
    """A business rule was violated (duplicate username, insufficient stock, ...)."""


class AuthenticationError(BusinessRuleError):
    """Login failed."""

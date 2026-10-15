"""Peru-specific validations."""

# SUNAT taxpayer prefixes: 10 natural person, 15/17 special cases, 20 company.
RUC_PREFIXES = ("10", "15", "17", "20")
# Weights of SUNAT's modulo-11 check digit, applied to the first 10 digits.
RUC_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def ruc_check_digit(first_ten: str) -> int:
    """Compute the 11th digit of a RUC from its first 10 digits."""
    total = sum(int(digit) * weight for digit, weight in zip(first_ten, RUC_WEIGHTS))
    digit = 11 - (total % 11)
    return {10: 0, 11: 1}.get(digit, digit)


def ruc_problem(ruc: str) -> str | None:
    """Return why a RUC is invalid, or None if it is valid."""
    if len(ruc) != 11 or not ruc.isdigit():
        return "El RUC debe tener exactamente 11 dígitos."
    if not ruc.startswith(RUC_PREFIXES):
        return "El RUC debe empezar con 10, 15, 17 o 20."
    if ruc_check_digit(ruc[:10]) != int(ruc[10]):
        return "El RUC no es válido (dígito verificador incorrecto)."
    return None


def is_valid_ruc(ruc: str) -> bool:
    return ruc_problem(ruc) is None

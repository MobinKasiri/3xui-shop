"""Number formatting for bot messages (Western digits 0-9)."""

_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def to_persian_digits(text: str | int | float) -> str:
    """Format a value for display using Western numerals."""
    return str(text)


def normalize_digits(text: str) -> str:
    """Accept user input typed with Persian or Western digits."""
    return text.translate(_FA_TO_EN)


def format_toman(amount: int) -> str:
    """Format integer Toman amount with comma separators."""
    return f"{amount:,}"

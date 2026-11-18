"""
Choice lists, and one small helper, that more than one app needs.

They live in "entries" because it is the app the others build on: "evidence"
imports from "entries" (its citations point at fact sheets and actions), so
"entries" must not import from "evidence".
"""

from django.db import models
from django.utils import formats


class Language(models.TextChoices):
    """The language a source, a quote or an excerpt is in."""

    MALAYALAM = "ml", "Malayalam"
    ENGLISH = "en", "English"
    OTHER = "other", "Other"


class DatePrecision(models.TextChoices):
    """
    How much of a stored date is actually known.

    The database always holds a full date. With "month" the day is not known,
    and with "year" neither the day nor the month is. The date is kept exactly
    as it was typed: the unknown part is only hidden when the date is shown.
    """

    DAY = "day", "Day"
    MONTH = "month", "Month"
    YEAR = "year", "Year"


# How a date is written out for each precision, in Django's date-format
# letters: j = day of the month, F = full month name, Y = four-digit year.
_DATE_FORMATS = {
    DatePrecision.DAY: "j F Y",
    DatePrecision.MONTH: "F Y",
    DatePrecision.YEAR: "Y",
}


def format_partial_date(value, precision):
    """
    Write a date out, leaving off the part that `precision` says is unknown.

    For 5 March 2023: "5 March 2023" (day), "March 2023" (month), "2023" (year).
    An empty date gives an empty string.
    """
    if value is None:
        return ""
    # An unexpected precision is treated as "day", so nothing is hidden by mistake.
    date_format = _DATE_FORMATS.get(precision, _DATE_FORMATS[DatePrecision.DAY])
    return formats.date_format(value, date_format)

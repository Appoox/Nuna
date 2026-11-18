"""Tests for the shared choice lists and the partial-date helper."""

from datetime import date

from django.test import SimpleTestCase

from entries.choices import DatePrecision, Language, format_partial_date


class ChoiceListTests(SimpleTestCase):
    """The stored values of the shared lists are the ones the specification names."""

    def test_language_values(self):
        """Languages are stored as ml, en and other."""
        self.assertEqual(Language.values, ["ml", "en", "other"])

    def test_precision_values(self):
        """Date precisions are stored as day, month and year."""
        self.assertEqual(DatePrecision.values, ["day", "month", "year"])


class FormatPartialDateTests(SimpleTestCase):
    """A date is written out only as far as its precision says it is known."""

    # The date used in every test: 5 March 2023.
    DATE = date(2023, 3, 5)

    def test_day_precision_shows_the_full_date(self):
        """With "day" nothing is hidden."""
        self.assertEqual(format_partial_date(self.DATE, DatePrecision.DAY), "5 March 2023")

    def test_month_precision_hides_the_day(self):
        """With "month" only the month and the year are shown."""
        self.assertEqual(format_partial_date(self.DATE, DatePrecision.MONTH), "March 2023")

    def test_year_precision_shows_only_the_year(self):
        """With "year" only the year is shown."""
        self.assertEqual(format_partial_date(self.DATE, DatePrecision.YEAR), "2023")

    def test_no_date_gives_an_empty_string(self):
        """An empty date is written as nothing, whatever the precision."""
        self.assertEqual(format_partial_date(None, DatePrecision.MONTH), "")

    def test_unknown_precision_shows_the_full_date(self):
        """A precision that is not in the list hides nothing."""
        self.assertEqual(format_partial_date(self.DATE, "unexpected"), "5 March 2023")

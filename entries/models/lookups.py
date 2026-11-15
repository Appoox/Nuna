"""
Lookup lists that entries pick from: speakers and topics.

Each speaker and each topic is entered once and then chosen from a list,
so the same person or subject is always the same database row.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from wagtail.admin.panels import FieldPanel
from wagtail.search import index


class BilingualName(models.Model):
    """
    An English name and a Malayalam name, at least one of which is filled in.

    Abstract: it has no table of its own. Its fields and rules are copied
    into every model that inherits from it.
    """

    name_en = models.CharField("name (English)", max_length=200, blank=True)
    name_ml = models.CharField("name (Malayalam)", max_length=200, blank=True)

    class Meta:
        abstract = True
        # List alphabetically by English name, then by Malayalam name.
        ordering = ["name_en", "name_ml"]
        constraints = [
            # The database itself refuses a row with no name at all, so the
            # rule holds even for data that does not come through a form.
            # %(app_label)s and %(class)s give each model its own constraint name.
            models.CheckConstraint(
                condition=~(Q(name_en="") & Q(name_ml="")),
                name="%(app_label)s_%(class)s_has_a_name",
            ),
        ]

    def clean(self):
        """Tidy the names and require at least one of them."""
        super().clean()
        # Remove stray spaces, so "  " does not count as a name.
        self.name_en = self.name_en.strip()
        self.name_ml = self.name_ml.strip()
        if not self.name_en and not self.name_ml:
            # Shown next to the English name field in the admin form.
            raise ValidationError({"name_en": "Enter a name in English, in Malayalam, or in both."})

    def __str__(self):
        """Show the English name, or the Malayalam name when there is no English one."""
        return self.name_en or self.name_ml


class Speaker(BilingualName, index.Indexed, models.Model):
    """
    Someone or something that makes statements or takes actions.

    A speaker is either a person (for example a minister) or a body (for
    example a department). The speaker's title is not stored here: it is
    stored with each statement, because titles change over time.
    """

    class Kind(models.TextChoices):
        """Whether the speaker is one person or an organisation."""

        PERSON = "person", "Person"
        BODY = "body", "Body"

    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.PERSON,
        help_text="A body is an organisation, such as a department, rather than one person.",
    )

    # The fields shown on the add/edit form in the Wagtail admin, in order.
    panels = [
        FieldPanel("kind"),
        FieldPanel("name_en"),
        FieldPanel("name_ml"),
    ]

    # What the admin's search box looks at. SearchField matches whole words,
    # AutocompleteField matches as you type, FilterField allows filtering.
    search_fields = [
        index.SearchField("name_en"),
        index.SearchField("name_ml"),
        index.AutocompleteField("name_en"),
        index.AutocompleteField("name_ml"),
        index.FilterField("kind"),
    ]

    class Meta(BilingualName.Meta):
        verbose_name = "speaker"
        verbose_name_plural = "speakers"


class Topic(BilingualName, index.Indexed, models.Model):
    """A subject area, such as finance or health, that entries are tagged with."""

    # The fields shown on the add/edit form in the Wagtail admin, in order.
    panels = [
        FieldPanel("name_en"),
        FieldPanel("name_ml"),
    ]

    # What the admin's search box looks at (see Speaker.search_fields).
    search_fields = [
        index.SearchField("name_en"),
        index.SearchField("name_ml"),
        index.AutocompleteField("name_en"),
        index.AutocompleteField("name_ml"),
    ]

    class Meta(BilingualName.Meta):
        verbose_name = "topic"
        verbose_name_plural = "topics"

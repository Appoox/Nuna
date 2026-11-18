"""
Sources and their saved copies.

A source is one piece of evidence: a video, a news article, a newspaper
clipping, an official document, a social media post. It is entered once and
can then back any number of entries.

A saved copy ("capture") keeps the source reachable if the original goes
away: a Wayback Machine link, an archive.today link, or the file itself
stored on this server.
"""

import hashlib
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel
from wagtail.models import Orderable
from wagtail.search import index

from entries.choices import DatePrecision, Language, format_partial_date

# The only host a Wayback Machine link may be on. archive.today links are not
# checked, because that site is reached under many changing addresses.
WAYBACK_HOST = "web.archive.org"


def sha256_of(file):
    """
    Return the SHA-256 hash of a file as 64 hexadecimal characters.

    The file is read in pieces, so a large video never has to fit in memory.
    """
    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    # Go back to the start, so that whoever reads the file next gets all of it.
    file.seek(0)
    return digest.hexdigest()


class Source(index.Indexed, ClusterableModel):
    """
    One piece of evidence that entries can cite.

    ClusterableModel lets the saved copies be edited inside this model's own
    form and saved together with it. Sources keep no version history.
    """

    class Kind(models.TextChoices):
        """What the source is."""

        VIDEO = "video", "Video"
        NEWS_ARTICLE = "news_article", "News article"
        NEWSPAPER_CLIPPING = "newspaper_clipping", "Newspaper clipping"
        OFFICIAL_DOCUMENT = "official_document", "Official document"
        SOCIAL_MEDIA_POST = "social_media_post", "Social media post"
        OTHER = "other", "Other"

    # No default: the kind has to be chosen for every source.
    kind = models.CharField(max_length=30, choices=Kind.choices)
    # One title, in the source's own language. It is not translated.
    title = models.CharField(max_length=500, help_text="In the source's own language.")
    # Plain text on purpose: there is no shared list of outlets.
    publisher = models.CharField(
        max_length=200,
        blank=True,
        help_text="Who published it: the newspaper, channel, department or account.",
    )
    language = models.CharField(max_length=10, choices=Language.choices, blank=True)
    published_on = models.DateField(
        "published on",
        null=True,
        blank=True,
        help_text="If only the month or the year is known, pick any day in it and set the precision.",
    )
    published_on_precision = models.CharField(
        "precision",
        max_length=10,
        choices=DatePrecision.choices,
        default=DatePrecision.DAY,
        help_text="How much of the date is known. The rest of it is not shown.",
    )
    # Long enough for real addresses, which often run to several hundred characters.
    original_url = models.URLField(
        "original URL",
        max_length=2000,
        blank=True,
        help_text="Where the source is, or was, online. Leave empty for a source that was never online.",
    )
    # Internal: the API and the downloads must never include this field.
    notes = models.TextField(blank=True, help_text="For your own use. Never shown publicly.")

    # The fields shown on the add/edit form in the Wagtail admin, in order.
    panels = [
        FieldPanel("kind"),
        FieldPanel("title"),
        FieldPanel("publisher"),
        FieldPanel("language"),
        # The date and its precision sit side by side.
        FieldRowPanel(
            [
                FieldPanel("published_on"),
                FieldPanel("published_on_precision"),
            ],
            heading="Published",
        ),
        FieldPanel("original_url"),
        FieldPanel("notes"),
        # The saved copies, edited right here in the source's form. The
        # fields of each copy are listed in Capture.panels.
        InlinePanel("captures", heading="Saved copies", label="Saved copy"),
    ]

    # What the admin's search box looks at. SearchField matches whole words,
    # AutocompleteField matches as you type, FilterField allows filtering.
    # `notes` is left out on purpose, so that internal text can never
    # influence a search that is later offered to the public.
    search_fields = [
        index.SearchField("title"),
        index.AutocompleteField("title"),
        index.SearchField("publisher"),
        index.AutocompleteField("publisher"),
        index.SearchField("original_url"),
        index.FilterField("kind"),
        index.FilterField("language"),
    ]

    class Meta:
        verbose_name = "source"
        verbose_name_plural = "sources"
        # Newest added first: a source that was just entered is at the top.
        ordering = ["-id"]

    def clean(self):
        """Tidy the title and require one that is more than spaces."""
        super().clean()
        self.title = self.title.strip()
        if not self.title:
            raise ValidationError({"title": "Enter a title."})

    def __str__(self):
        """A source is shown by its title."""
        return self.title

    def published_display(self):
        """The publication date as far as it is known, for example "March 2023"."""
        return format_partial_date(self.published_on, self.published_on_precision)

    # Column heading in the admin list, and the field the column sorts by.
    published_display.short_description = "published"
    published_display.admin_order_field = "published_on"

    def copy_count(self):
        """How many saved copies the source has."""
        return self.captures.count()

    # Column heading in the admin list.
    copy_count.short_description = "saved copies"

    def sources_with_same_url(self):
        """
        Other sources whose original URL is exactly the same as this one's.

        Sharing a URL is allowed; the admin only warns about it after saving.
        A source without a URL matches nothing.
        """
        if not self.original_url:
            return Source.objects.none()
        return Source.objects.filter(original_url=self.original_url).exclude(pk=self.pk)


class Capture(Orderable):
    """
    A saved copy of a source.

    Orderable gives the copies a fixed order inside their source, which can
    be changed in the form. The copies are edited inside the source's form.
    """

    class Method(models.TextChoices):
        """How the copy was made."""

        WAYBACK = "wayback", "Wayback Machine"
        ARCHIVE_TODAY = "archive_today", "archive.today"
        STORED_FILE = "stored_file", "Stored file"

    class Status(models.TextChoices):
        """Where an automatic Wayback capture stands. A copy added by hand is always OK."""

        PENDING = "pending", "Pending"
        OK = "ok", "OK"
        FAILED = "failed", "Failed"

    # ParentalKey ties the copy to its source and lets both be saved together.
    # Deleting a source deletes its copies' rows (the files stay on disk).
    source = ParentalKey(Source, on_delete=models.CASCADE, related_name="captures")
    # No default: the method has to be chosen for every copy.
    method = models.CharField(max_length=20, choices=Method.choices)
    url = models.URLField(
        "link",
        max_length=2000,
        blank=True,
        help_text=(
            "Wayback Machine and archive.today: the link to the archived copy. "
            "Stored file: optional, the address the file was downloaded from."
        ),
    )
    # Files keep their own name, inside a folder for the year and month of
    # the upload, for example captures/2026/11/Budget_speech.pdf.
    # max_length leaves room for long file names (Django's default is 100).
    file = models.FileField(
        upload_to="captures/%Y/%m/",
        max_length=500,
        blank=True,
        help_text="For a stored file only: the complete file. Stored files are public.",
    )
    # Worked out from the file when it is uploaded; never typed in.
    sha256 = models.CharField(
        "SHA-256",
        max_length=64,
        blank=True,
        editable=False,
        help_text="Fingerprint of the stored file, worked out when it is uploaded.",
    )
    captured_at = models.DateTimeField(
        "captured at",
        default=timezone.now,
        help_text="When the copy was made. Starts as the time you add it; change it if you know better.",
    )
    # The next three fields belong to the automatic Wayback capture. A copy
    # added by hand keeps the defaults: status OK, no job ID, no error.
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OK)
    job_id = models.CharField("job ID", max_length=100, blank=True)
    error = models.TextField(blank=True)

    # The fields of one saved copy on the source's form, in order. Status,
    # job ID and error are not on the form: nothing sets them by hand.
    panels = [
        FieldPanel("method"),
        FieldPanel("url"),
        FieldPanel("file"),
        FieldPanel("captured_at"),
        # Shown, but not editable.
        FieldPanel("sha256", read_only=True),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "saved copy"
        verbose_name_plural = "saved copies"

    def __str__(self):
        """A copy is shown by its method, for example "Wayback Machine"."""
        return self.get_method_display()

    def has_new_upload(self):
        """
        True when the file was just uploaded and is not on disk yet.

        `_committed` is Django's own marker for that: it is False from the
        moment a file is uploaded until it has been written to storage.
        """
        return bool(self.file) and not self.file._committed

    def clean(self):
        """
        Check that the copy has what its method needs.

        - Wayback Machine and archive.today: a link, and no file. A Wayback
          link must be on web.archive.org.
        - Stored file: a file. A link is optional.
        """
        super().clean()
        # Collected by field name, so each message appears beside its field.
        errors = {}

        if self.method in (self.Method.WAYBACK, self.Method.ARCHIVE_TODAY):
            if self.file:
                errors["file"] = (
                    f"A {self.get_method_display()} copy is a link. "
                    'Remove the file, or change the method to "Stored file".'
                )
            # An automatic Wayback capture that is still pending, or that
            # failed, has no link yet. Every other link copy needs one.
            waiting_for_wayback = self.method == self.Method.WAYBACK and self.status != self.Status.OK
            if not self.url:
                if not waiting_for_wayback:
                    errors["url"] = "Enter the link to the archived copy."
            elif self.method == self.Method.WAYBACK:
                host = (urlsplit(self.url).hostname or "").lower()
                if host != WAYBACK_HOST:
                    errors["url"] = f"A Wayback Machine link must be on {WAYBACK_HOST}."

        elif self.method == self.Method.STORED_FILE:
            if not self.file:
                errors["file"] = "Upload the file."
            elif self.has_new_upload():
                # Only a new upload is checked. A file that is already stored
                # is never refused later because the rules changed.
                file_error = self._new_upload_error()
                if file_error:
                    errors["file"] = file_error

        # A copy with no method gets Django's own "This field is required".

        if errors:
            raise ValidationError(errors)

    def _new_upload_error(self):
        """Return why a newly uploaded file is refused, or None if it is fine."""
        # The type is judged by the file name's extension, in any letter case.
        extension = Path(self.file.name).suffix.lower().lstrip(".")
        if extension not in settings.STORED_FILE_EXTENSIONS:
            allowed = ", ".join(settings.STORED_FILE_EXTENSIONS)
            shown = f".{extension}" if extension else "no extension"
            return f"This type of file ({shown}) cannot be stored. Allowed: {allowed}."
        # 1 MB is counted as 1024 x 1024 bytes.
        if self.file.size > settings.STORED_FILE_MAX_MB * 1024 * 1024:
            return f"The file is larger than the limit of {settings.STORED_FILE_MAX_MB} MB."
        return None

    def save(self, *args, **kwargs):
        """Work out the SHA-256 hash whenever the file changes, then save."""
        if not self.file:
            # No file (a link copy, or the file was removed): no hash.
            self.sha256 = ""
        elif self.has_new_upload():
            self.sha256 = sha256_of(self.file)
        # A file that is already on disk keeps the hash it has.
        super().save(*args, **kwargs)

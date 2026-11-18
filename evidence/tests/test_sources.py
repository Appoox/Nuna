"""Tests for sources and their saved copies."""

import hashlib
import shutil
import tempfile
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from wagtail.test.utils.form_data import inline_formset, nested_form_data

from evidence.models import Capture, Source

# Addresses used in several tests. example.org is reserved for examples, and
# no test ever contacts any of these.
ARTICLE_URL = "https://news.example.org/budget-speech"
WAYBACK_URL = "https://web.archive.org/web/20261115000000/https://news.example.org/budget-speech"
ARCHIVE_TODAY_URL = "https://archive.ph/AbCdE"

# A Malayalam title: "Budget speech".
BUDGET_SPEECH_ML = "ബജറ്റ് പ്രസംഗം"

# The contents of a pretend PDF. Only its bytes matter, not its format.
PDF_BYTES = b"%PDF-1.7 pretend document for the tests"


def make_source(**fields):
    """Create and return a saved source, with a kind and a title unless given."""
    fields.setdefault("kind", Source.Kind.NEWS_ARTICLE)
    fields.setdefault("title", "Budget speech report")
    return Source.objects.create(**fields)


def upload(name="order.pdf", content=PDF_BYTES):
    """Return a file as the browser would send it in an upload."""
    return SimpleUploadedFile(name, content)


class TemporaryMediaMixin:
    """
    Send uploaded files to a throw-away folder that is removed after the tests.

    Without it, test uploads would land among the real uploaded files.
    """

    @classmethod
    def setUpClass(cls):
        """Point MEDIA_ROOT at a new temporary folder for this test class."""
        media_folder = tempfile.mkdtemp()
        media_setting = override_settings(MEDIA_ROOT=media_folder)
        media_setting.enable()
        # Clean-ups run in reverse order: first restore the setting, then
        # delete the folder.
        cls.addClassCleanup(shutil.rmtree, media_folder, ignore_errors=True)
        cls.addClassCleanup(media_setting.disable)
        super().setUpClass()


class SourceTests(TestCase):
    """The rules and behaviour of a source by itself."""

    def test_kind_and_title_are_required(self):
        """A source with nothing filled in fails on its kind and its title."""
        with self.assertRaises(ValidationError) as caught:
            Source().full_clean()
        self.assertIn("kind", caught.exception.message_dict)
        self.assertIn("title", caught.exception.message_dict)

    def test_kind_and_title_are_enough(self):
        """Language, publisher, date, original URL and notes may all stay empty."""
        source = Source(kind=Source.Kind.NEWSPAPER_CLIPPING, title=BUDGET_SPEECH_ML)
        source.full_clean()  # raises ValidationError if the model is invalid
        source.save()
        self.assertEqual(str(source), BUDGET_SPEECH_ML)

    def test_title_of_spaces_is_rejected(self):
        """A title made only of spaces does not count as a title."""
        with self.assertRaises(ValidationError) as caught:
            Source(kind=Source.Kind.VIDEO, title="   ").full_clean()
        self.assertIn("title", caught.exception.message_dict)

    def test_title_is_trimmed(self):
        """Spaces around the title are removed during validation."""
        source = Source(kind=Source.Kind.VIDEO, title="  Press meet  ")
        source.full_clean()
        self.assertEqual(source.title, "Press meet")

    def test_kinds_offered(self):
        """The kinds are the agreed list: no "archive_link", and social media posts included."""
        self.assertEqual(
            Source.Kind.values,
            ["video", "news_article", "newspaper_clipping", "official_document", "social_media_post", "other"],
        )

    def test_kind_outside_the_list_is_rejected(self):
        """The removed kind "archive_link" can no longer be saved through validation."""
        with self.assertRaises(ValidationError) as caught:
            Source(kind="archive_link", title="Old page").full_clean()
        self.assertIn("kind", caught.exception.message_dict)

    def test_precision_defaults_to_day(self):
        """A new source's publication date counts as a full date unless told otherwise."""
        self.assertEqual(Source().published_on_precision, "day")

    def test_published_date_is_shown_as_far_as_it_is_known(self):
        """The precision decides how much of the publication date is shown."""
        source = Source(published_on=date(2023, 3, 5))
        for precision, expected in (("day", "5 March 2023"), ("month", "March 2023"), ("year", "2023")):
            with self.subTest(precision=precision):
                source.published_on_precision = precision
                self.assertEqual(source.published_display(), expected)

    def test_source_without_a_date_shows_no_date(self):
        """No publication date gives an empty text, not an error."""
        self.assertEqual(Source().published_display(), "")

    def test_partial_date_is_stored_as_typed(self):
        """With month or year precision the stored day and month are left exactly as entered."""
        source = make_source(published_on=date(2023, 3, 17), published_on_precision="year")
        source.full_clean()
        source.save()
        source.refresh_from_db()
        self.assertEqual(source.published_on, date(2023, 3, 17))

    def test_newest_source_is_listed_first(self):
        """The default order puts the most recently added source at the top."""
        make_source(title="Added first")
        make_source(title="Added second")
        self.assertEqual(list(Source.objects.values_list("title", flat=True)), ["Added second", "Added first"])

    def test_two_sources_may_share_an_original_url(self):
        """A second source with the same original URL passes validation and is saved."""
        first = make_source(title="First", original_url=ARTICLE_URL)
        second = Source(kind=Source.Kind.NEWS_ARTICLE, title="Second", original_url=ARTICLE_URL)
        second.full_clean()
        second.save()
        # Each of the two finds the other one.
        self.assertEqual(list(first.sources_with_same_url()), [second])
        self.assertEqual(list(second.sources_with_same_url()), [first])

    def test_sources_without_a_url_never_match_each_other(self):
        """An empty original URL is not "the same URL" as another empty one."""
        first = make_source(title="Clipping one")
        make_source(title="Clipping two")
        self.assertEqual(list(first.sources_with_same_url()), [])

    def test_different_urls_do_not_match(self):
        """Only exactly the same address counts as shared."""
        first = make_source(title="First", original_url=ARTICLE_URL)
        make_source(title="Second", original_url=ARTICLE_URL + "?page=2")
        self.assertEqual(list(first.sources_with_same_url()), [])


class CaptureRuleTests(TestCase):
    """What each method of saved copy must have. Nothing is saved to disk here."""

    def setUp(self):
        """Every saved copy needs a source to belong to."""
        self.source = make_source()

    def capture(self, **fields):
        """Return an unsaved copy of the test source."""
        return Capture(source=self.source, **fields)

    def errors_of(self, capture):
        """Validate a copy that is expected to fail, and return its errors by field name."""
        with self.assertRaises(ValidationError) as caught:
            capture.full_clean()
        return caught.exception.message_dict

    def test_method_is_required(self):
        """A copy must say how it was made."""
        self.assertIn("method", self.errors_of(self.capture(url=ARCHIVE_TODAY_URL)))

    def test_new_copy_is_ok_and_captured_now(self):
        """A copy added by hand has the status OK and, unless changed, the current time."""
        before = timezone.now()
        capture = self.capture(method="archive_today", url=ARCHIVE_TODAY_URL)
        self.assertEqual(capture.status, "ok")
        self.assertEqual(capture.job_id, "")
        self.assertEqual(capture.error, "")
        self.assertGreaterEqual(capture.captured_at, before)
        self.assertLessEqual(capture.captured_at, timezone.now())

    def test_wayback_copy_with_a_wayback_link_is_valid(self):
        """A Wayback Machine copy may be added by hand with a web.archive.org link."""
        self.capture(method="wayback", url=WAYBACK_URL).full_clean()

    def test_wayback_copy_needs_a_link(self):
        """A Wayback Machine copy added by hand without a link is refused."""
        self.assertIn("url", self.errors_of(self.capture(method="wayback")))

    def test_wayback_link_must_be_on_web_archive_org(self):
        """Pasting the original address, or an archive.today link, as a Wayback link is refused."""
        for url in (ARTICLE_URL, ARCHIVE_TODAY_URL, "https://archive.org/details/something"):
            with self.subTest(url=url):
                errors = self.errors_of(self.capture(method="wayback", url=url))
                self.assertEqual(errors["url"], ["A Wayback Machine link must be on web.archive.org."])

    def test_wayback_host_is_matched_in_any_letter_case(self):
        """WEB.ARCHIVE.ORG is the same host as web.archive.org."""
        self.capture(method="wayback", url="https://WEB.ARCHIVE.ORG/web/2026/https://news.example.org/").full_clean()

    def test_automatic_wayback_copy_may_wait_without_a_link(self):
        """A Wayback capture that is pending, or that failed, has no link yet and is still valid."""
        for status in ("pending", "failed"):
            with self.subTest(status=status):
                self.capture(method="wayback", status=status).full_clean()

    def test_archive_today_copy_needs_a_link(self):
        """An archive.today copy without a link is refused."""
        self.assertIn("url", self.errors_of(self.capture(method="archive_today")))

    def test_archive_today_link_is_not_checked_against_a_host(self):
        """archive.today uses many addresses, so any valid address is accepted."""
        for url in (ARCHIVE_TODAY_URL, "https://archive.md/AbCdE", "https://archive.is/AbCdE"):
            with self.subTest(url=url):
                self.capture(method="archive_today", url=url).full_clean()

    def test_link_copies_refuse_a_file(self):
        """A Wayback Machine or archive.today copy with a file attached is refused."""
        for method, url in (("wayback", WAYBACK_URL), ("archive_today", ARCHIVE_TODAY_URL)):
            with self.subTest(method=method):
                errors = self.errors_of(self.capture(method=method, url=url, file=upload()))
                self.assertIn("file", errors)

    def test_stored_file_copy_needs_a_file(self):
        """A stored-file copy without a file is refused."""
        errors = self.errors_of(self.capture(method="stored_file"))
        self.assertEqual(errors["file"], ["Upload the file."])

    def test_stored_file_copy_may_have_a_link(self):
        """A stored file is valid with or without the address it was downloaded from."""
        self.capture(method="stored_file", file=upload()).full_clean()
        self.capture(method="stored_file", file=upload(), url=ARTICLE_URL).full_clean()

    def test_every_allowed_file_type_is_accepted(self):
        """Each extension in the agreed list passes, in small or capital letters."""
        self.assertEqual(
            settings.STORED_FILE_EXTENSIONS,
            # Documents, images, video, audio, saved web pages.
            ["pdf", "jpg", "jpeg", "png", "webp", "mp4", "webm", "mkv", "mov", "mp3", "m4a", "ogg", "wav", "html", "mhtml"],
        )
        for extension in settings.STORED_FILE_EXTENSIONS:
            for name in (f"file.{extension}", f"FILE.{extension.upper()}"):
                with self.subTest(name=name):
                    self.capture(method="stored_file", file=upload(name)).full_clean()

    def test_other_file_types_are_refused(self):
        """A file whose extension is not in the list, or that has none, is refused."""
        for name in ("program.exe", "page.htm", "archive.zip", "noextension"):
            with self.subTest(name=name):
                errors = self.errors_of(self.capture(method="stored_file", file=upload(name)))
                self.assertIn("cannot be stored", errors["file"][0])

    @override_settings(STORED_FILE_MAX_MB=1)
    def test_file_over_the_size_limit_is_refused(self):
        """With a limit of 1 MB, a file of exactly 1 MB passes and one byte more is refused."""
        one_megabyte = 1024 * 1024
        self.capture(method="stored_file", file=upload(content=b"x" * one_megabyte)).full_clean()
        errors = self.errors_of(self.capture(method="stored_file", file=upload(content=b"x" * (one_megabyte + 1))))
        self.assertEqual(errors["file"], ["The file is larger than the limit of 1 MB."])

    def test_size_limit_is_500_mb_unless_changed(self):
        """The agreed limit. It is read from STORED_FILE_MAX_MB, which is not set in the tests."""
        self.assertEqual(settings.STORED_FILE_MAX_MB, 500)


class StoredFileTests(TemporaryMediaMixin, TestCase):
    """What happens when a stored file is actually written to disk."""

    def setUp(self):
        """Every saved copy needs a source to belong to."""
        self.source = make_source()

    def store(self, name="order.pdf", content=PDF_BYTES):
        """Save a stored-file copy of the test source and return it."""
        return Capture.objects.create(source=self.source, method="stored_file", file=upload(name, content))

    def test_hash_is_worked_out_on_upload(self):
        """Saving a stored file records the SHA-256 hash of its contents."""
        capture = self.store()
        self.assertEqual(capture.sha256, hashlib.sha256(PDF_BYTES).hexdigest())
        self.assertEqual(len(capture.sha256), 64)

    def test_stored_file_is_complete_on_disk(self):
        """The file on disk holds exactly the uploaded bytes, also after hashing read it once."""
        capture = self.store()
        with capture.file.open("rb") as stored:
            self.assertEqual(stored.read(), PDF_BYTES)

    def test_hash_of_a_file_larger_than_one_read(self):
        """A file that is read in several pieces gets the right hash."""
        # Django reads files 64 KB at a time; 200 KB takes four reads.
        content = bytes(range(256)) * 800
        capture = self.store("recording.mp3", content)
        self.assertEqual(capture.sha256, hashlib.sha256(content).hexdigest())
        with capture.file.open("rb") as stored:
            self.assertEqual(stored.read(), content)

    def test_big_upload_held_in_a_temporary_file_is_hashed_and_stored(self):
        """
        Django holds uploads over 2.5 MB in a temporary file instead of in memory.

        Videos always arrive that way, so the hash and the stored file must be right then too.
        """
        content = b"0123456789abcdef" * (200 * 1024)  # 3.2 MB
        big_upload = TemporaryUploadedFile("recording.mp4", "video/mp4", len(content), None)
        big_upload.write(content)
        big_upload.seek(0)
        capture = Capture.objects.create(source=self.source, method="stored_file", file=big_upload)
        self.assertEqual(capture.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(capture.file.size, len(content))
        with capture.file.open("rb") as stored:
            self.assertEqual(hashlib.sha256(stored.read()).hexdigest(), capture.sha256)

    def test_file_keeps_its_name_in_a_dated_folder(self):
        """The file goes to captures/<year>/<month>/ under its own name."""
        capture = self.store("Budget_speech.pdf")
        today = timezone.now()
        self.assertEqual(capture.file.name, f"captures/{today:%Y}/{today:%m}/Budget_speech.pdf")

    def test_second_file_with_the_same_name_does_not_replace_the_first(self):
        """Two uploads with one name are both kept: the second gets extra letters in its name."""
        first = self.store("order.pdf", b"first file")
        second = self.store("order.pdf", b"second file")
        self.assertNotEqual(first.file.name, second.file.name)
        with first.file.open("rb") as stored:
            self.assertEqual(stored.read(), b"first file")

    def test_link_copy_has_no_hash(self):
        """A copy without a file has an empty hash."""
        capture = Capture.objects.create(source=self.source, method="archive_today", url=ARCHIVE_TODAY_URL)
        self.assertEqual(capture.sha256, "")

    def test_replacing_the_file_updates_the_hash(self):
        """Uploading a different file to the same copy records the new file's hash."""
        capture = self.store("order.pdf", b"first version")
        capture.file = upload("order-corrected.pdf", b"second version")
        capture.save()
        capture.refresh_from_db()
        self.assertEqual(capture.sha256, hashlib.sha256(b"second version").hexdigest())

    def test_saving_again_keeps_the_hash(self):
        """Saving a copy whose file did not change leaves the hash alone."""
        capture = self.store()
        capture = Capture.objects.get(pk=capture.pk)
        capture.url = ARTICLE_URL
        capture.save()
        self.assertEqual(capture.sha256, hashlib.sha256(PDF_BYTES).hexdigest())

    def test_removing_the_file_clears_the_hash(self):
        """A copy whose file is taken away no longer carries a hash."""
        capture = self.store()
        capture.method = "archive_today"
        capture.url = ARCHIVE_TODAY_URL
        capture.file = ""
        capture.save()
        self.assertEqual(capture.sha256, "")

    def test_file_already_stored_is_not_refused_when_the_rules_change(self):
        """A stored file stays valid even if its type is later taken off the list."""
        capture = Capture.objects.get(pk=self.store().pk)
        with override_settings(STORED_FILE_EXTENSIONS=["png"], STORED_FILE_MAX_MB=0):
            capture.full_clean()

    def test_deleting_a_source_removes_its_copies_but_not_the_file(self):
        """Deleting a source deletes the rows of its copies; the stored file stays on disk."""
        capture = self.store()
        storage, name = capture.file.storage, capture.file.name
        self.source.delete()
        self.assertFalse(Capture.objects.exists())
        self.assertTrue(storage.exists(name))


class AdminScreenTests(TemporaryMediaMixin, TestCase):
    """The Wagtail admin screens for sources, used as a superuser."""

    LIST_URL_NAME = "wagtailsnippets_evidence_source:list"
    ADD_URL_NAME = "wagtailsnippets_evidence_source:add"
    EDIT_URL_NAME = "wagtailsnippets_evidence_source:edit"

    def setUp(self):
        """Log in as a superuser, who may see and change everything."""
        user = get_user_model().objects.create_superuser(
            username="editor", email="editor@example.com", password="not-a-real-password"
        )
        self.client.force_login(user)

    def form_data(self, captures=(), **fields):
        """
        Return what the browser posts from the source form.

        `fields` override the source's own fields. `captures` is a list with
        one dictionary per saved copy on the form.
        """
        data = {
            "kind": "news_article",
            "title": "Budget speech report",
            "publisher": "",
            "language": "",
            "published_on": "",
            "published_on_precision": "day",
            "original_url": "",
            "notes": "",
        }
        data.update(fields)
        # Every copy on the form posts a capture time; the form fills it in with "now".
        copies = [{"url": "", "captured_at": "2026-11-15 10:30", **copy} for copy in captures]
        data["captures"] = inline_formset(copies)
        return nested_form_data(data)

    def add(self, captures=(), **fields):
        """Post the add form and return the response, without following the redirect."""
        return self.client.post(reverse(self.ADD_URL_NAME), self.form_data(captures, **fields))

    def test_list_screen_loads(self):
        """The list screen for sources opens."""
        self.assertEqual(self.client.get(reverse(self.LIST_URL_NAME)).status_code, 200)

    def test_sources_are_in_the_main_menu(self):
        """The admin's main menu links to the list of sources."""
        html = self.client.get(reverse("wagtailadmin_home")).content.decode()
        self.assertIn(reverse(self.LIST_URL_NAME), html)

    def test_add_form_shows_the_saved_copies_section(self):
        """The add screen opens and offers saved copies inside the source's form."""
        response = self.client.get(reverse(self.ADD_URL_NAME))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved copies")
        # The management field every inline section posts.
        self.assertContains(response, 'name="captures-TOTAL_FORMS"')

    def test_source_can_be_added_with_kind_and_title_only(self):
        """Submitting the add form with just a kind and a title creates the source."""
        response = self.add(kind="newspaper_clipping", title=BUDGET_SPEECH_ML)
        # A successful save redirects back to the list.
        self.assertRedirects(response, reverse(self.LIST_URL_NAME))
        source = Source.objects.get()
        self.assertEqual((source.kind, source.title), ("newspaper_clipping", BUDGET_SPEECH_ML))
        self.assertEqual(source.captures.count(), 0)

    def test_add_form_refuses_a_source_without_a_title(self):
        """Submitting the add form without a title shows the form again and saves nothing."""
        response = self.add(title="")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertEqual(Source.objects.count(), 0)

    def test_source_can_be_added_with_all_three_kinds_of_copy(self):
        """One source is saved together with a Wayback link, an archive.today link and a stored file."""
        response = self.add(
            original_url=ARTICLE_URL,
            captures=[
                {"method": "wayback", "url": WAYBACK_URL},
                {"method": "archive_today", "url": ARCHIVE_TODAY_URL},
                {"method": "stored_file", "file": upload("page.pdf")},
            ],
        )
        self.assertRedirects(response, reverse(self.LIST_URL_NAME))
        captures = list(Source.objects.get().captures.all())
        # The copies keep the order they had on the form.
        self.assertEqual([capture.method for capture in captures], ["wayback", "archive_today", "stored_file"])
        # Copies added by hand are OK at once and have no job behind them.
        self.assertEqual({capture.status for capture in captures}, {"ok"})
        self.assertEqual({capture.job_id for capture in captures}, {""})
        stored = captures[2]
        self.assertEqual(stored.sha256, hashlib.sha256(PDF_BYTES).hexdigest())
        self.assertTrue(stored.file.name.endswith("/page.pdf"))

    def test_capture_time_typed_on_the_form_is_kept(self):
        """The time entered for a copy is saved as Indian time, not replaced by "now"."""
        self.add(captures=[{"method": "archive_today", "url": ARCHIVE_TODAY_URL, "captured_at": "2024-02-29 18:45"}])
        captured_at = timezone.localtime(Capture.objects.get().captured_at)
        self.assertEqual(f"{captured_at:%Y-%m-%d %H:%M %Z}", "2024-02-29 18:45 IST")

    def test_add_form_refuses_a_stored_file_copy_without_a_file(self):
        """A stored-file copy with no file shows the form again and saves nothing."""
        response = self.add(captures=[{"method": "stored_file"}])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload the file.")
        self.assertEqual(Source.objects.count(), 0)

    def test_add_form_refuses_a_file_of_the_wrong_type(self):
        """Uploading a file type that is not on the list shows an error and saves nothing."""
        response = self.add(captures=[{"method": "stored_file", "file": upload("program.exe")}])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This type of file (.exe) cannot be stored.")
        self.assertEqual(Source.objects.count(), 0)

    def test_add_form_refuses_a_wayback_link_on_another_site(self):
        """A Wayback copy whose link is the original address is refused."""
        response = self.add(captures=[{"method": "wayback", "url": ARTICLE_URL}])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Wayback Machine link must be on web.archive.org.")
        self.assertEqual(Source.objects.count(), 0)

    def test_saving_a_second_source_with_the_same_url_warns(self):
        """The second source is saved, and the next screen names the first one."""
        first = make_source(title="First report", original_url=ARTICLE_URL)
        response = self.client.post(
            reverse(self.ADD_URL_NAME),
            self.form_data(title="Second report", original_url=ARTICLE_URL),
            follow=True,  # go on to the list screen, where the messages are shown
        )
        self.assertEqual(Source.objects.count(), 2)
        self.assertContains(response, "Another source has the same original URL: “First report”.")
        # The warning carries a button that opens the other source.
        self.assertContains(response, reverse(self.EDIT_URL_NAME, args=[first.pk]))

    def test_warning_counts_the_sources_it_does_not_name(self):
        """With many sources on one URL, three are named and the rest are counted."""
        for number in range(1, 6):
            make_source(title=f"Report {number}", original_url=ARTICLE_URL)
        response = self.client.post(
            reverse(self.ADD_URL_NAME),
            self.form_data(title="Report 6", original_url=ARTICLE_URL),
            follow=True,
        )
        # Newest first: reports 5, 4 and 3 are named, 2 and 1 are counted.
        self.assertContains(
            response, "5 other sources have the same original URL: “Report 5”, “Report 4”, “Report 3” and 2 more."
        )

    def test_editing_a_source_that_shares_its_url_warns_too(self):
        """The warning also follows a save from the edit screen."""
        make_source(title="First report", original_url=ARTICLE_URL)
        second = make_source(title="Second report", original_url=ARTICLE_URL)
        response = self.client.post(
            reverse(self.EDIT_URL_NAME, args=[second.pk]),
            self.form_data(title="Second report, corrected", original_url=ARTICLE_URL),
            follow=True,
        )
        second.refresh_from_db()
        self.assertEqual(second.title, "Second report, corrected")
        self.assertContains(response, "Another source has the same original URL: “First report”.")

    def test_no_warning_when_the_url_is_not_shared(self):
        """Sources with different URLs, or with none, save without a warning."""
        make_source(title="First report", original_url=ARTICLE_URL)
        for url in (ARTICLE_URL + "?page=2", ""):
            with self.subTest(url=url):
                response = self.client.post(
                    reverse(self.ADD_URL_NAME), self.form_data(title="Another", original_url=url), follow=True
                )
                self.assertNotContains(response, "same original URL")

    def test_edit_screen_shows_the_hash_of_a_stored_file(self):
        """The edit screen of a source opens and displays the stored file's SHA-256 hash."""
        source = make_source()
        capture = Capture.objects.create(source=source, method="stored_file", file=upload())
        response = self.client.get(reverse(self.EDIT_URL_NAME, args=[source.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, capture.sha256)

    def test_copy_can_be_removed_on_the_edit_screen(self):
        """Marking a copy as deleted on the form removes it and keeps the other one."""
        source = make_source()
        kept = Capture.objects.create(source=source, method="wayback", url=WAYBACK_URL, sort_order=0)
        removed = Capture.objects.create(source=source, method="archive_today", url=ARCHIVE_TODAY_URL, sort_order=1)
        data = self.form_data()
        # Describe the two existing copies as the edit form posts them.
        data.update(
            nested_form_data(
                {
                    "captures": inline_formset(
                        [
                            {"id": kept.pk, "method": "wayback", "url": WAYBACK_URL, "captured_at": "2026-11-15 10:30"},
                            {
                                "id": removed.pk,
                                "method": "archive_today",
                                "url": ARCHIVE_TODAY_URL,
                                "captured_at": "2026-11-15 10:30",
                                "DELETE": "1",
                            },
                        ],
                        initial=2,
                    )
                }
            )
        )
        response = self.client.post(reverse(self.EDIT_URL_NAME, args=[source.pk]), data)
        self.assertRedirects(response, reverse(self.LIST_URL_NAME))
        self.assertEqual(list(source.captures.values_list("pk", flat=True)), [kept.pk])

    def test_list_shows_the_date_as_far_as_known_and_the_number_of_copies(self):
        """The list has a "published" column that respects the precision, and counts the copies."""
        source = make_source(published_on=date(2023, 3, 5), published_on_precision="month")
        Capture.objects.create(source=source, method="wayback", url=WAYBACK_URL)
        Capture.objects.create(source=source, method="archive_today", url=ARCHIVE_TODAY_URL)
        response = self.client.get(reverse(self.LIST_URL_NAME))
        self.assertContains(response, "March 2023")
        self.assertNotContains(response, "5 March 2023")
        # The two column headings that come from methods of Source.
        self.assertContains(response, "Published")
        self.assertContains(response, "Saved copies")

    def test_search_finds_a_source_by_title_or_publisher(self):
        """The list's search box matches the title, in either script, and the publisher."""
        make_source(title=BUDGET_SPEECH_ML, publisher="Kerala Daily")
        make_source(title="Road repair order", publisher="Public Works Department")
        list_url = reverse(self.LIST_URL_NAME)
        for query in ("ബജറ്റ്", "Daily"):
            with self.subTest(query=query):
                response = self.client.get(list_url, {"q": query})
                self.assertContains(response, BUDGET_SPEECH_ML)
                self.assertNotContains(response, "Road repair order")

    def test_list_can_be_filtered_by_kind(self):
        """Choosing a kind in the filters leaves only sources of that kind."""
        make_source(kind="video", title="Press meet recording")
        make_source(kind="social_media_post", title="Post about the bridge")
        response = self.client.get(reverse(self.LIST_URL_NAME), {"kind": "social_media_post"})
        self.assertContains(response, "Post about the bridge")
        self.assertNotContains(response, "Press meet recording")

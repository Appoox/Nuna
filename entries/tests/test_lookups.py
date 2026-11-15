"""Tests for the lookup lists: speakers and topics."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from entries.models import Speaker, Topic

# A Malayalam name used in several tests: "Finance Department".
FINANCE_DEPARTMENT_ML = "ധനകാര്യ വകുപ്പ്"
# A Malayalam topic name: "Health".
HEALTH_ML = "ആരോഗ്യം"


class NameRuleTests(TestCase):
    """At least one of the two names must be filled in, for speakers and topics alike."""

    def test_english_name_alone_is_enough(self):
        """A speaker with only an English name passes validation."""
        speaker = Speaker(name_en="Finance Department", kind=Speaker.Kind.BODY)
        speaker.full_clean()  # raises ValidationError if the model is invalid
        speaker.save()
        self.assertEqual(str(speaker), "Finance Department")

    def test_malayalam_name_alone_is_enough(self):
        """A speaker with only a Malayalam name passes validation and is shown by it."""
        speaker = Speaker(name_ml=FINANCE_DEPARTMENT_ML, kind=Speaker.Kind.BODY)
        speaker.full_clean()
        speaker.save()
        self.assertEqual(str(speaker), FINANCE_DEPARTMENT_ML)

    def test_no_name_at_all_is_rejected_by_validation(self):
        """A speaker or topic with neither name fails validation, with the error on name_en."""
        for model in (Speaker, Topic):
            with self.subTest(model=model.__name__), self.assertRaises(ValidationError) as caught:
                model().full_clean()
            self.assertIn("name_en", caught.exception.message_dict)

    def test_spaces_do_not_count_as_a_name(self):
        """Names made only of spaces are treated as empty."""
        with self.assertRaises(ValidationError):
            Topic(name_en="   ", name_ml="  ").full_clean()

    def test_names_are_trimmed(self):
        """Spaces around a name are removed during validation."""
        topic = Topic(name_en="  Health ", name_ml=f" {HEALTH_ML}  ")
        topic.full_clean()
        self.assertEqual(topic.name_en, "Health")
        self.assertEqual(topic.name_ml, HEALTH_ML)

    def test_database_refuses_a_row_with_no_name(self):
        """Even without form validation, the database rejects a nameless row."""
        for model in (Speaker, Topic):
            # transaction.atomic() keeps the failed insert from breaking the test's own transaction.
            with self.subTest(model=model.__name__), self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create()


class SpeakerTests(TestCase):
    """Behaviour specific to speakers."""

    def test_kind_defaults_to_person(self):
        """A new speaker is a person unless told otherwise."""
        self.assertEqual(Speaker(name_en="Someone").kind, Speaker.Kind.PERSON)

    def test_english_name_is_preferred_for_display(self):
        """When both names exist, the English one is used as the label."""
        speaker = Speaker(name_en="Finance Department", name_ml=FINANCE_DEPARTMENT_ML)
        self.assertEqual(str(speaker), "Finance Department")

    def test_speakers_are_listed_alphabetically(self):
        """The default order is by English name."""
        Speaker.objects.create(name_en="Revenue Department")
        Speaker.objects.create(name_en="Finance Department")
        names = list(Speaker.objects.values_list("name_en", flat=True))
        self.assertEqual(names, ["Finance Department", "Revenue Department"])


class AdminScreenTests(TestCase):
    """The Wagtail admin screens for speakers and topics."""

    def setUp(self):
        """Log in as a superuser, who may see and change everything."""
        user = get_user_model().objects.create_superuser(
            username="editor", email="editor@example.com", password="not-a-real-password"
        )
        self.client.force_login(user)

    def test_list_screens_load(self):
        """The list screens for speakers and topics open."""
        for url_name in ("wagtailsnippets_entries_speaker:list", "wagtailsnippets_entries_topic:list"):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_both_models_are_in_the_main_menu(self):
        """The admin's main menu links to the speaker and topic lists."""
        html = self.client.get(reverse("wagtailadmin_home")).content.decode()
        self.assertIn(reverse("wagtailsnippets_entries_speaker:list"), html)
        self.assertIn(reverse("wagtailsnippets_entries_topic:list"), html)

    def test_speaker_can_be_added_with_a_malayalam_name_only(self):
        """Submitting the add form with only a Malayalam name creates the speaker."""
        response = self.client.post(
            reverse("wagtailsnippets_entries_speaker:add"),
            {"kind": "body", "name_en": "", "name_ml": FINANCE_DEPARTMENT_ML},
        )
        # A successful save redirects back to the list.
        self.assertRedirects(response, reverse("wagtailsnippets_entries_speaker:list"))
        self.assertTrue(Speaker.objects.filter(name_ml=FINANCE_DEPARTMENT_ML, kind="body").exists())

    def test_add_form_refuses_a_topic_with_no_name(self):
        """Submitting the add form with both names empty shows the form again and saves nothing."""
        response = self.client.post(
            reverse("wagtailsnippets_entries_topic:add"), {"name_en": "", "name_ml": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a name in English, in Malayalam, or in both.")
        self.assertEqual(Topic.objects.count(), 0)

    def test_search_finds_a_speaker_by_either_name(self):
        """The list's search box matches the English and the Malayalam name."""
        Speaker.objects.create(name_en="Finance Department", name_ml=FINANCE_DEPARTMENT_ML, kind="body")
        Speaker.objects.create(name_en="Revenue Department", kind="body")
        list_url = reverse("wagtailsnippets_entries_speaker:list")
        for query in ("Finance", "ധനകാര്യ"):
            with self.subTest(query=query):
                response = self.client.get(list_url, {"q": query})
                self.assertContains(response, "Finance Department")
                self.assertNotContains(response, "Revenue Department")

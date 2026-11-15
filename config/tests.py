"""
Smoke tests for the project scaffold.

They prove that Django and Wagtail start, that the database works and that
the main routes answer. Run them with `python manage.py test`.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ScaffoldSmokeTests(TestCase):
    """The basics every later change relies on."""

    def test_admin_login_page_loads(self):
        """The Wagtail admin login page is served."""
        response = self.client.get(reverse("wagtailadmin_login"))
        self.assertEqual(response.status_code, 200)

    def test_admin_requires_login(self):
        """An anonymous visitor to the admin is sent to the login page."""
        response = self.client.get(reverse("wagtailadmin_home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("wagtailadmin_login"), response["Location"])

    def test_superuser_can_open_admin(self):
        """A superuser can log in and see the admin dashboard."""
        user = get_user_model().objects.create_superuser(
            username="editor", email="editor@example.com", password="not-a-real-password"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("wagtailadmin_home"))
        self.assertEqual(response.status_code, 200)

    def test_public_root_is_served(self):
        """The public root address answers with Wagtail's default welcome page."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

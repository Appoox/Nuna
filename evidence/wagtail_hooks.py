"""
Wagtail admin screens for the "evidence" app.

Wagtail imports this module by itself at start-up. The viewset below gives
sources their list, add, edit and delete screens, and their own item in the
admin's main menu. Saved copies have no screens of their own: they are
edited inside the form of their source.

Menu positions (menu_order) are listed in entries/wagtail_hooks.py.
Sources are at 130.
"""

from django.contrib.admin.utils import quote
from django.urls import reverse
from wagtail.admin import messages
from wagtail.admin.views import generic
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import CreateView, EditView, SnippetViewSet

from .models import Source

# The warning names at most this many other sources, and counts the rest.
SAME_URL_WARNING_LIMIT = 3


class SameUrlWarningMixin:
    """
    After a source is saved, warn if other sources have the same original URL.

    Two sources may share a URL, so nothing is refused: the source is saved
    first and the warning appears on the next screen, with a button to open
    each of the other sources.
    """

    def save_action(self):
        """Let Wagtail finish the save and build its answer, then add the warning."""
        response = super().save_action()
        # self.object is the source that was just saved.
        others = self.object.sources_with_same_url()
        total = others.count()
        if total:
            shown = list(others[:SAME_URL_WARNING_LIMIT])
            titles = ", ".join(f"“{other}”" for other in shown)
            if total > len(shown):
                titles += f" and {total - len(shown)} more"
            if total == 1:
                text = f"Another source has the same original URL: {titles}."
            else:
                text = f"{total} other sources have the same original URL: {titles}."
            messages.warning(
                self.request,
                text,
                # One button per named source, leading to its edit screen.
                buttons=[
                    messages.button(reverse(self.edit_url_name, args=(quote(other.pk),)), f"Open “{other}”")
                    for other in shown
                ],
            )
        return response


class SourceCreateView(SameUrlWarningMixin, CreateView):
    """The "add source" screen, with the same-URL warning."""


class SourceCopyView(generic.CopyViewMixin, SourceCreateView):
    """The "copy source" screen: an add screen that starts from an existing source."""


class SourceEditView(SameUrlWarningMixin, EditView):
    """The "edit source" screen, with the same-URL warning."""


class SourceViewSet(SnippetViewSet):
    """Admin screens for sources."""

    model = Source
    icon = "doc-full"
    menu_label = "Sources"
    menu_name = "sources"
    menu_order = 130
    # Put the item in the main menu and not under Wagtail's "Snippets" item.
    add_to_admin_menu = True
    # Columns of the list screen. The last two are methods of Source.
    list_display = ["title", "kind", "publisher", "published_display", "copy_count"]
    # Filters offered beside the list.
    list_filter = ["kind", "language"]
    # Wagtail's own screens, extended with the same-URL warning.
    add_view_class = SourceCreateView
    copy_view_class = SourceCopyView
    edit_view_class = SourceEditView


# Tell Wagtail about the viewset.
register_snippet(SourceViewSet)

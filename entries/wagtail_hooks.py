"""
Wagtail admin screens for the "entries" app.

Wagtail imports this module by itself at start-up. Each "viewset" below
gives one model its list, add, edit and delete screens, and its own item
in the admin's main menu.

Menu positions (menu_order) used by this project, lowest first:
    110 Fact sheets, 120 Actions, 130 Sources, 140 Speakers, 150 Topics
Fact sheets and Actions are added by later changes. Sources has its screens
in evidence/wagtail_hooks.py. Wagtail's own "Pages" item is at 100 and
"Images" at 300, so these items sit between the two.
"""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Speaker, Topic


class SpeakerViewSet(SnippetViewSet):
    """Admin screens for speakers."""

    model = Speaker
    icon = "user"
    menu_label = "Speakers"
    menu_name = "speakers"
    menu_order = 140
    # Put the item in the main menu and not under Wagtail's "Snippets" item.
    add_to_admin_menu = True
    # Columns of the list screen.
    list_display = ["name_en", "name_ml", "kind"]
    # Filters offered beside the list.
    list_filter = ["kind"]


class TopicViewSet(SnippetViewSet):
    """Admin screens for topics."""

    model = Topic
    icon = "tag"
    menu_label = "Topics"
    menu_name = "topics"
    menu_order = 150
    # Put the item in the main menu and not under Wagtail's "Snippets" item.
    add_to_admin_menu = True
    # Columns of the list screen.
    list_display = ["name_en", "name_ml"]


# Tell Wagtail about both viewsets.
register_snippet(SpeakerViewSet)
register_snippet(TopicViewSet)

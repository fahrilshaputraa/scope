"""Regression tests for the H4 accessibility and mobile audit.

These assertions target stable, meaningful rules (landmarks, headings, labels,
accessible names, scroll regions, dialog semantics, validation feedback) rather
than snapshotting markup.
"""

import re
from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import Project
from apps.work.models import Task

pytestmark = pytest.mark.django_db

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class PageParser:
    """Collect elements with their attributes and descendant text."""

    def __init__(self):
        from html.parser import HTMLParser

        class Parser(HTMLParser):
            def __init__(self, owner):
                super().__init__(convert_charrefs=True)
                self.owner = owner

            def handle_starttag(self, tag, attrs):
                if tag == "svg":
                    for element in self.owner.open:
                        element["svgs"] += 1
                element = {"tag": tag, "attrs": dict(attrs), "text": [], "svgs": 0}
                self.owner.open.append(element)
                if tag in VOID_ELEMENTS:
                    self.handle_endtag(tag)

            def handle_startendtag(self, tag, attrs):
                self.handle_starttag(tag, attrs)
                self.handle_endtag(tag)

            def handle_endtag(self, tag):
                for index in range(len(self.owner.open) - 1, -1, -1):
                    if self.owner.open[index]["tag"] == tag:
                        self.owner.elements.append(self.owner.open.pop(index))
                        return

            def handle_data(self, data):
                for element in self.owner.open:
                    element["text"].append(data)

        self.elements = []
        self.open = []
        self._parser = Parser(self)

    def feed(self, markup):
        self._parser.feed(markup)
        return self

    def find(self, tag=None, predicate=None):
        for element in self.elements:
            if tag and element["tag"] != tag:
                continue
            if predicate and not predicate(element):
                continue
            yield element


def parse(response):
    return PageParser().feed(response.content.decode())


@pytest.fixture
def workspace(db):
    pm = User.objects.create_user("owner", password="valid-password", is_staff=True)
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("member", password="valid-password")
    project = Project.objects.create(
        name="Accessibility project",
        code="A11Y",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    project.members.add(member)
    task = Task.objects.create(
        project=project,
        title="Audit page",
        assignee=member,
        start_date=date(2026, 10, 2),
        due_date=date(2026, 10, 10),
    )
    return {"pm": pm, "member": member, "project": project, "task": task}


def authenticated_pages(workspace):
    return {
        "dashboard": reverse("projects:dashboard"),
        "project_list": reverse("projects:project_list"),
        "project_detail": reverse("projects:project_detail", args=[workspace["project"].pk]),
        "project_progress": reverse("projects:project_progress", args=[workspace["project"].pk]),
        "project_timeline": reverse("projects:project_timeline", args=[workspace["project"].pk]),
        "project_issues": reverse("projects:project_issues", args=[workspace["project"].pk]),
        "issue_list": reverse("work:issue_list"),
        "my_tasks": reverse("work:my_tasks"),
        "task_form": reverse("work:task_update", args=[workspace["task"].pk]),
        "task_detail": reverse("work:task_detail", args=[workspace["task"].pk]),
        "user_list": reverse("identity:user_list"),
        "user_edit": reverse("identity:user_edit", args=[workspace["member"].pk]),
        "search": reverse("projects:search"),
    }


def test_login_page_has_one_main_and_one_heading(client):
    response = client.get(reverse("identity:login"))
    page = parse(response)
    assert len(list(page.find("main"))) == 1
    assert len(list(page.find("h1"))) == 1


@pytest.mark.parametrize(
    "page_name",
    [
        "dashboard",
        "project_list",
        "project_detail",
        "project_progress",
        "project_timeline",
        "project_issues",
        "issue_list",
        "my_tasks",
        "task_form",
        "task_detail",
        "user_list",
        "user_edit",
        "search",
    ],
)
def test_workspace_pages_have_one_main_one_h1_and_skip_link(client, workspace, page_name):
    client.force_login(workspace["pm"])
    response = client.get(authenticated_pages(workspace)[page_name])
    assert response.status_code == 200
    page = parse(response)

    assert len(list(page.find("main"))) == 1
    assert len(list(page.find("h1"))) == 1
    assert any(
        element["attrs"].get("class", "") == "skip-link"
        and element["attrs"].get("href") == "#main-content"
        for element in page.find("a")
    )
    assert any(element["attrs"].get("id") == "main-content" for element in page.find("main"))


@pytest.mark.parametrize(
    "page_name",
    ["dashboard", "project_detail", "task_detail", "issue_list", "project_list"],
)
def test_icon_only_controls_have_accessible_names(client, workspace, page_name):
    client.force_login(workspace["pm"])
    response = client.get(authenticated_pages(workspace)[page_name])
    page = parse(response)
    for element in page.find():
        if element["tag"] not in {"a", "button"} or not element["svgs"]:
            continue
        if "".join(element["text"]).strip():
            continue
        attrs = element["attrs"]
        assert attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("title"), (
            f"{page_name}: icon-only <{element['tag']}> has no accessible name"
        )


def test_action_drawer_is_a_labelled_modal_dialog(client, workspace):
    client.force_login(workspace["pm"])
    page = parse(client.get(reverse("projects:dashboard")))
    dialogs = list(page.find("dialog"))
    assert len(dialogs) == 1
    dialog = dialogs[0]
    assert dialog["attrs"].get("aria-modal") == "true"
    assert dialog["attrs"].get("aria-label") or dialog["attrs"].get("aria-labelledby")
    assert any(
        "data-panel-status" in element["attrs"] for element in page.find()
    )


@pytest.mark.parametrize(
    "page_name",
    [
        "dashboard",
        "project_list",
        "project_detail",
        "project_progress",
        "project_timeline",
        "issue_list",
        "user_list",
    ],
)
def test_horizontal_scroll_regions_are_focusable_and_labelled(client, workspace, page_name):
    client.force_login(workspace["pm"])
    response = client.get(authenticated_pages(workspace)[page_name])
    page = parse(response)
    regions = [
        element
        for element in page.find()
        if any(
            token in element["attrs"].get("class", "")
            for token in ("overflow-x-auto", "task-timeline-scroll", "portfolio-map-scroll")
        )
    ]
    assert regions, f"{page_name}: expected at least one horizontal scroll region"
    for region in regions:
        assert region["attrs"].get("role") == "region"
        assert region["attrs"].get("tabindex") == "0"
        assert region["attrs"].get("aria-label")


@pytest.mark.parametrize("page_name", ["task_form", "user_edit"])
def test_form_controls_are_labelled_and_required_state_is_exposed(
    client, workspace, page_name
):
    client.force_login(workspace["pm"])
    response = client.get(authenticated_pages(workspace)[page_name])
    assert response.status_code == 200
    page = parse(response)
    labels = {
        element["attrs"]["for"]
        for element in page.find("label")
        if element["attrs"].get("for")
    }
    controls = [
        element
        for element in page.find()
        if element["tag"] in {"input", "select", "textarea"}
        and element["attrs"].get("type") not in {"hidden", "submit", "button"}
    ]
    assert controls
    for control in controls:
        attrs = control["attrs"]
        identifier = attrs.get("id")
        assert attrs.get("aria-label") or (identifier and identifier in labels), (
            f"{page_name}: control {identifier or attrs.get('name')} has no label"
        )
        if "required" in attrs:
            assert attrs.get("aria-required") == "true"


def test_field_errors_are_announced_and_associated(client, workspace):
    client.force_login(workspace["pm"])
    url = reverse("identity:user_edit", args=[workspace["member"].pk])
    response = client.post(url, {"username": "", "role": Role.MEMBER})
    assert response.status_code == 200
    page = parse(response)

    errors = [
        element
        for element in page.find()
        if element["attrs"].get("id") == "error-username"
    ]
    assert errors
    assert errors[0]["attrs"].get("role") == "alert"

    username = next(
        element
        for element in page.find("input")
        if element["attrs"].get("id") == "id_username"
    )
    assert username["attrs"].get("aria-invalid") == "true"
    described_by = username["attrs"].get("aria-describedby", "")
    assert "error-username" in described_by
    assert "help-username" in described_by


def test_help_text_and_required_state_are_exposed(client, workspace):
    client.force_login(workspace["pm"])
    page = parse(
        client.get(reverse("identity:user_edit", args=[workspace["member"].pk]))
    )
    username = next(
        element
        for element in page.find("input")
        if element["attrs"].get("id") == "id_username"
    )
    assert "help-username" in username["attrs"].get("aria-describedby", "")
    assert username["attrs"].get("aria-required") == "true"
    assert any(element["attrs"].get("id") == "help-username" for element in page.find())


def test_login_authentication_error_uses_alert(client):
    response = client.post(
        reverse("identity:login"),
        {"username": "nobody", "password": "wrong-password"},
    )
    assert response.status_code == 200
    page = parse(response)
    alerts = [element for element in page.find() if element["attrs"].get("role") == "alert"]
    assert alerts
    assert any(
        element["attrs"].get("for") == "username" for element in page.find("label")
    )
    assert any(
        element["attrs"].get("for") == "password" for element in page.find("label")
    )


def test_templates_keep_images_alt_and_svgs_decorative():
    """Static guard against regressions in long-tail templates."""
    for path in sorted(TEMPLATES.rglob("*.html")):
        source = path.read_text()
        for image in re.findall(r"<img\b[^>]*>", source):
            assert "alt=" in image, f"{path}: <img> without alt"
        for svg in re.findall(r"<svg\b[^>]*>", source):
            assert "aria-hidden" in svg or 'role="img"' in svg, (
                f"{path}: decorative <svg> must be aria-hidden or a labelled image"
            )

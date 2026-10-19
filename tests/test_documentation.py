from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.documentation import ARTICLES
from apps.identity.models import Role
from apps.projects.models import Project

pytestmark = pytest.mark.django_db


@pytest.fixture
def docs_user():
    return User.objects.create_user("docs-reader", password="valid-password")


@pytest.mark.parametrize("slug", [None, "progress-proyek"])
def test_documentation_requires_login(client, slug):
    url = reverse("identity:docs_article", args=[slug]) if slug else reverse("identity:docs")
    response = client.get(url)
    assert response.status_code == 302
    assert response.url.startswith(reverse("identity:login") + "?next=")


@pytest.mark.parametrize("article", ARTICLES, ids=lambda item: item["slug"])
def test_every_guide_renders_with_section_navigation(client, docs_user, article):
    client.force_login(docs_user)
    response = client.get(reverse("identity:docs_article", args=[article["slug"]]))
    assert response.status_code == 200
    html = response.content.decode()
    assert article["title"] in html
    assert 'class="project-sidebar settings-sidebar"' in html
    assert 'aria-label="Bagian pengaturan"' in html
    for block in article["sections"]:
        assert f'id="{block["id"]}"' in html
        assert f'href="#{block["id"]}"' in html
    if any(block.get("visual") for block in article["sections"]):
        assert "Data ilustrasi" in html
        assert "Contoh untuk belajar" in html


@pytest.mark.parametrize("role", [Role.MEMBER, Role.MANAGEMENT, Role.PROJECT_MANAGER])
def test_docs_are_available_to_all_roles_but_creation_links_follow_permissions(
    client, docs_user, role
):
    docs_user.pcc_profile.role = role
    docs_user.pcc_profile.save()
    client.force_login(docs_user)
    response = client.get(reverse("identity:docs_article", args=["membuat-proyek"]))
    assert response.status_code == 200
    assert (reverse("projects:project_create") in response.content.decode()) == (
        role == Role.PROJECT_MANAGER
    )


def test_staff_can_follow_project_creation_guide(client, docs_user):
    docs_user.is_staff = True
    docs_user.save()
    client.force_login(docs_user)
    response = client.get(reverse("identity:docs_article", args=["membuat-proyek"]))
    assert reverse("projects:project_create") in response.content.decode()


def test_search_covers_body_and_tables_without_exposing_project_data(client, docs_user):
    Project.objects.create(
        name="Proyek rahasia qzxprivat",
        code="SECRET-DOCS",
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 10, 30),
    )
    client.force_login(docs_user)
    response = client.get(reverse("identity:docs"), {"q": "10 MB"})
    slugs = [match["article"]["slug"] for match in response.context["search_results"]]
    assert "komentar-lampiran" in slugs
    assert "task-kanban" not in slugs
    assert "progress-proyek" not in slugs
    assert "qzxprivat" not in response.content.decode()
    response = client.get(reverse("identity:docs"), {"q": "qzxprivat"})
    assert not response.context["search_results"]
    assert "Belum ada topik yang cocok" in response.content.decode()
    assert "Proyek rahasia" not in response.content.decode()


def test_search_requires_all_terms_and_escapes_query(client, docs_user):
    client.force_login(docs_user)
    response = client.get(reverse("identity:docs"), {"q": "  LAMPIRAN   10 MB "})
    assert response.context["query"] == "LAMPIRAN 10 MB"
    assert response.context["search_results"]
    response = client.get(reverse("identity:docs"), {"q": "lampiran qzxmissing"})
    assert not response.context["search_results"]
    response = client.get(reverse("identity:docs"), {"q": "<script>alert(1)</script>"})
    html = response.content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    response = client.get(reverse("identity:docs"), {"q": "base"})
    assert any(
        match["article"]["slug"] == "jadwal-baseline"
        for match in response.context["search_results"]
    )


def test_unknown_topic_and_post_do_not_change_data(client, docs_user):
    client.force_login(docs_user)
    count = Project.objects.count()
    assert client.get(reverse("identity:docs_article", args=["tidak-ada"])).status_code == 404
    assert client.post(reverse("identity:docs"), {"progress": "100"}).status_code == 405
    assert Project.objects.count() == count


def test_settings_submenu_preserves_profile_form(client, docs_user):
    client.force_login(docs_user)
    response = client.get(reverse("identity:settings"))
    html = response.content.decode()
    assert reverse("identity:docs") in html
    assert 'class="project-sidebar settings-sidebar"' in html
    assert 'value="profile"' in html
    assert 'value="password"' in html
    assert 'class="settings-help"' not in html

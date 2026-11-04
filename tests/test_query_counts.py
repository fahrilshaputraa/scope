"""Jumlah query halaman utama tidak boleh tumbuh seiring jumlah project (anti N+1)."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.projects.models import (
    LifecycleStatus,
    Milestone,
    Phase,
    ProgressBaselinePoint,
    Project,
    Risk,
)
from apps.work.models import Issue, Task, TaskStatus

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()

#: Selisih query yang diizinkan saat jumlah project bertambah (nol idealnya).
SLACK = 2

PAGES = {
    "dashboard": lambda p: reverse("projects:dashboard"),
    "project_list": lambda p: reverse("projects:project_list"),
    "reports": lambda p: reverse("projects:reports"),
    "progress_task": lambda p: reverse("projects:progress_task"),
    "control_index": lambda p: reverse("projects:control_index"),
    "timeline_global": lambda p: reverse("projects:timeline_global"),
    "project_detail": lambda p: reverse("projects:project_detail", args=[p.pk]),
    "project_control": lambda p: reverse("projects:project_control", args=[p.pk]),
    "project_tasks": lambda p: reverse("projects:project_tasks", args=[p.pk]),
    "issue_list": lambda p: reverse("work:issue_list"),
}

TASK_PAGES = ["project_detail", "project_tasks", "progress_task", "project_control"]


def make_user(name, role):
    user = User.objects.create_user(name, password="valid-password")
    assign_roles(user, [role])
    return user


def add_project(index, owner, workers):
    """Satu project lengkap: phase, milestone, risiko, issue, baseline, task, subtask."""
    manager = make_user(f"pm{index}", Role.PROJECT_MANAGER)
    project = Project.objects.create(
        name=f"Project {index}",
        code=f"P{index}",
        manager=manager,
        owner=owner,
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
        start_date=TODAY - timedelta(days=30),
        target_end_date=TODAY + timedelta(days=30),
    )
    project.members.add(*workers)
    phase = Phase.objects.create(project=project, name="Build", sequence=1)
    Milestone.objects.create(project=project, name="Rilis", date=TODAY + timedelta(days=10))
    Risk.objects.create(project=project, title="Risiko", severity="high", status="open")
    Issue.objects.create(project=project, title="Gawat", severity="critical")
    for offset, percent in ((-30, 0), (0, 50), (30, 100)):
        ProgressBaselinePoint.objects.create(
            project=project, date=TODAY + timedelta(days=offset), planned_percent=percent
        )
    statuses = [TaskStatus.DONE, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.REVIEW]
    first = None
    for n, status in enumerate(statuses):
        task = Task.objects.create(
            project=project,
            phase=phase,
            title=f"T{n}",
            status=status,
            assignee=workers[n % len(workers)],
            due_date=TODAY - timedelta(days=1) if n == 1 else TODAY + timedelta(days=5),
            blocked_reason="x" if status == TaskStatus.BLOCKED else "",
        )
        task.collaborators.add(workers[(n + 1) % len(workers)])
        first = first or task
    Task.objects.create(project=project, phase=phase, title="Detail", parent_task=first)
    return project


@pytest.fixture
def world():
    admin = make_user("adm", Role.ADMIN)
    owner = make_user("sponsor", Role.OWNER)
    workers = [make_user(f"worker{i}", Role.MEMBER) for i in range(3)]
    return admin, owner, workers


LAST = {"queries": []}


def count_queries(client, url):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    assert response.status_code == 200, url
    LAST["queries"] = [q["sql"] for q in queries.captured_queries]
    return len(queries)


def top_repeats():
    """Query yang paling sering berulang pada permintaan terakhir (untuk diagnosis)."""
    import re
    from collections import Counter

    normalized = (re.sub(r"\d+", "N", re.sub(r"'[^']*'", "S", q)) for q in LAST["queries"])
    counter = Counter(sql[:140] for sql in normalized)
    return "; ".join(f"{n}x {sql}" for sql, n in counter.most_common(2))


@pytest.mark.parametrize("page", list(PAGES))
def test_queries_do_not_grow_with_the_number_of_projects(client, world, page):
    admin, owner, workers = world
    projects = [add_project(i, owner, workers) for i in range(2)]
    client.force_login(admin)
    url_for = PAGES[page]
    client.get(url_for(projects[0]))  # hangatkan cache sesi dan ContentType
    few = count_queries(client, url_for(projects[0]))
    projects += [add_project(i, owner, workers) for i in range(2, 6)]
    many = count_queries(client, url_for(projects[0]))
    message = f"{page}: {few} query (2 project) -> {many} query (6 project). {top_repeats()}"
    assert many <= few + SLACK, message


@pytest.mark.parametrize("page", TASK_PAGES)
def test_queries_do_not_grow_with_the_number_of_tasks(client, world, page):
    admin, owner, workers = world
    project = add_project(0, owner, workers)
    client.force_login(admin)
    url = PAGES[page](project)
    client.get(url)
    few = count_queries(client, url)
    phase = project.phases.first()
    for n in range(12):
        task = Task.objects.create(
            project=project,
            phase=phase,
            title=f"Tambahan {n}",
            status=[TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.TODO][n % 3],
            assignee=workers[n % len(workers)],
            due_date=TODAY - timedelta(days=n + 1),
            blocked_reason="x",
        )
        task.collaborators.add(workers[(n + 1) % len(workers)])
        Task.objects.create(project=project, phase=phase, title=f"Sub {n}", parent_task=task)
    many = count_queries(client, url)
    message = f"{page}: {few} query (5 task) -> {many} query (29 task). {top_repeats()}"
    assert many <= few + SLACK, message

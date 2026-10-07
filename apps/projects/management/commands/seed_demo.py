"""Seed data demo PCC — proyek, phase, task, milestone, baseline, issue, notes.

Jalankan: uv run manage.py seed_demo
Idempoten: data demo (berdasarkan code project) dihapus lalu dibuat ulang.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.identity.models import Role, UserProfile
from apps.projects.models import (
    ActivityAction,
    ActivityEvent,
    Decision,
    Milestone,
    MilestoneStatus,
    Note,
    Phase,
    PhaseStatus,
    ProgressBaselinePoint,
    ProgressSnapshot,
    Project,
    ProjectStatus,
)
from apps.projects.services import actual_progress
from apps.work.models import (
    Issue,
    IssueStatus,
    Priority,
    Task,
    TaskStatus,
)

DEMO_CODES = ["HRMS-01", "LBR-02", "CP-03", "DWM-04", "SOC-05", "APG-06"]

TODAY = timezone.localdate()
D = lambda s: datetime.strptime(s, "%Y-%m-%d").date()  # noqa: E731
DEC = Decimal


class Command(BaseCommand):
    help = "Seed data demo PCC (6 project + data lengkap)"

    # --- helpers ---

    def user(self, username, role, first_name, title=""):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first_name, "email": f"{username}@example.com"},
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        changed = []
        if profile.role != role:
            profile.role = role
            changed.append("role")
        if title and profile.job_title != title:
            profile.job_title = title
            changed.append("job_title")
        if changed:
            profile.save(update_fields=changed + ["updated_at"])
        return user

    def baseline(self, project, rows):
        for date_str, percent, label in rows:
            ProgressBaselinePoint.objects.create(
                project=project,
                date=D(date_str),
                planned_percent=DEC(str(percent)),
                label=label,
            )

    def history(self, project, deltas):
        """Buat ProgressSnapshot dari baseline points (actual = planned + delta)."""
        today = timezone.localdate()
        live = actual_progress(project)
        for point in project.baseline_points.all():
            if point.date > today:
                continue
            delta = DEC(str(deltas.get(point.date.isoformat(), -2)))
            actual = point.planned_percent + delta
            if point.date == today:
                actual = live
            actual = max(DEC("0"), min(DEC("100"), actual))
            variance = (actual - point.planned_percent).quantize(DEC("0.01"))
            ProgressSnapshot.objects.update_or_create(
                project=project,
                date=point.date,
                defaults={
                    "planned_progress": point.planned_percent,
                    "actual_progress": actual,
                    "variance": variance,
                },
            )

    def activity(self, project, actor, action, message, ago):
        event = ActivityEvent.objects.create(
            project=project, actor=actor, action=action, message=message
        )
        ActivityEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - ago
        )

    def task(self, project, **kwargs):
        dates = kwargs.pop("dates", None)
        task = Task(project=project, **kwargs)
        if dates:
            task.start_date, task.due_date = (D(dates[0]), D(dates[1]))
        task.save()
        return task

    # --- main ---

    def handle(self, *args, **options):
        Project.objects.filter(code__in=DEMO_CODES).delete()

        fahril = self.user("fahril", Role.PROJECT_MANAGER, "Fahril", "Project Manager")
        andi = self.user("andi", Role.PROJECT_MANAGER, "Andi", "Project Manager")
        budi = self.user("budi", Role.MEMBER, "Budi", "Technical Lead")
        sari = self.user("sari", Role.MEMBER, "Sari", "Frontend Engineer")
        self.user("direksi", Role.MANAGEMENT, "Direksi", "Management")

        self._hrms(fahril, andi, budi, sari)
        self._lbr(andi, budi, sari)
        self._cp(budi, sari, andi)
        self._dwm(fahril, budi, sari)
        self._soc(andi)
        self._apg(budi, sari, andi)

        self.stdout.write(self.style.SUCCESS("Seed demo selesai: 6 project."))

    # ------------------------------------------------ PRD showcase project ---

    def _hrms(self, fahril, andi, budi, sari):
        p = Project.objects.create(
            code="HRMS-01",
            name="HRMS & VMS Implementation",
            description=(
                "Implementasi HRMS: employee master, scheduling, notification, "
                "dan vendor management system."
            ),
            manager=fahril,
            team="Platform",
            start_date=D("2026-08-03"),
            target_end_date=D("2026-10-30"),
            status=ProjectStatus.AT_RISK,
        )

        ph1 = Phase.objects.create(
            project=p, sequence=1, name="Discovery & Requirement",
            start_date=D("2026-08-03"), end_date=D("2026-08-14"),
            status=PhaseStatus.COMPLETED,
        )
        ph2 = Phase.objects.create(
            project=p, sequence=2, name="Foundation & Core",
            start_date=D("2026-08-17"), end_date=D("2026-09-11"),
            status=PhaseStatus.COMPLETED,
        )
        ph3 = Phase.objects.create(
            project=p, sequence=3, name="Features & Integration",
            start_date=D("2026-09-14"), end_date=D("2026-10-23"),
            status=PhaseStatus.IN_PROGRESS,
        )
        ph4 = Phase.objects.create(
            project=p, sequence=4, name="Testing & UAT",
            start_date=D("2026-10-26"), end_date=D("2026-10-30"),
            status=PhaseStatus.NOT_STARTED,
        )
        p.current_phase = ph3
        p.save(update_fields=["current_phase"])

        ms_req = Milestone.objects.create(
            project=p, name="Requirement Approved", date=D("2026-08-14"),
            status=MilestoneStatus.COMPLETED, owner=fahril,
            description="Requirement document disetujui stakeholder.",
        )
        ms_core = Milestone.objects.create(
            project=p, name="Core Development Complete", date=D("2026-09-11"),
            status=MilestoneStatus.COMPLETED, owner=budi,
        )
        ms_feat = Milestone.objects.create(
            project=p, name="Feature Complete", date=D("2026-10-23"),
            status=MilestoneStatus.IN_PROGRESS, owner=fahril,
        )
        Milestone.objects.create(
            project=p, name="UAT Start", date=D("2026-10-26"),
            status=MilestoneStatus.UPCOMING, owner=fahril,
            description="UAT entry criteria harus terpenuhi.",
        )
        Milestone.objects.create(
            project=p, name="Production Release", date=D("2026-10-30"),
            status=MilestoneStatus.UPCOMING, owner=fahril,
        )

        def t(title, phase, weight, status, progress, assignee, dates, **kw):
            return self.task(
                p, title=title, phase=phase, weight=weight, status=status,
                progress=DEC(progress), assignee=assignee, dates=dates, **kw,
            )

        _t_req = t("Requirement Gathering", ph1, 10, TaskStatus.DONE, "100", fahril,
                   ("2026-08-03", "2026-08-07"), labels="requirement",
                   milestone=ms_req, completed_at=timezone.now() - timedelta(days=54))
        t("UI/UX Design", ph1, 10, TaskStatus.DONE, "100", sari,
          ("2026-08-05", "2026-08-12"), labels="design", milestone=ms_req)
        t("Database Schema Design", ph2, 8, TaskStatus.DONE, "100", budi,
          ("2026-08-17", "2026-08-21"), labels="backend", milestone=ms_core)
        t("SSO & Authentication", ph2, 9, TaskStatus.DONE, "100", budi,
          ("2026-08-24", "2026-09-02"), labels="backend", milestone=ms_core)
        t("Admin CRUD Modules", ph2, 6, TaskStatus.DONE, "100", andi,
          ("2026-09-01", "2026-09-10"), labels="frontend", milestone=ms_core)
        t("Scheduler Engine", ph3, 7, TaskStatus.IN_PROGRESS, "70", fahril,
          ("2026-09-14", "2026-10-10"), labels="backend,critical-path",
          milestone=ms_feat, order=4)
        t("Notification API", ph3, 6, TaskStatus.IN_PROGRESS, "40", andi,
          ("2026-09-21", "2026-10-12"), labels="backend", milestone=ms_feat, order=5)
        t("Employee Dashboard", ph3, 8, TaskStatus.IN_PROGRESS, "55", sari,
          ("2026-09-14", "2026-10-16"), labels="frontend", milestone=ms_feat, order=6)
        t("Reporting Module", ph3, 6, TaskStatus.REVIEW, "80", andi,
          ("2026-09-28", "2026-10-14"), labels="frontend", milestone=ms_feat)
        t_int = t("Integration Testing", ph4, 7, TaskStatus.TODO, "0", budi,
                  ("2026-10-26", "2026-10-27"), labels="testing", order=1)
        t_perf = t("Performance Testing", ph4, 6, TaskStatus.BLOCKED, "0", budi,
                   ("2026-10-27", "2026-10-28"), labels="testing", order=2,
                   blocked_reason="Production-like environment belum tersedia.",
                   blocked_dependency="Infrastructure Team")
        t("UAT Preparation", ph4, 5, TaskStatus.TODO, "0", fahril,
          ("2026-10-26", "2026-10-28"), labels="testing", order=3)
        t("Documentation & Training", ph4, 6, TaskStatus.BACKLOG, "0", sari,
          ("2026-10-28", "2026-10-29"), labels="docs", order=4)
        t("Cutover & Release", ph4, 6, TaskStatus.BACKLOG, "0", fahril,
          ("2026-10-30", "2026-10-30"), labels="release", order=5)

        self.baseline(p, [
            ("2026-08-03", 0, "Start"),
            ("2026-08-10", 8, ""),
            ("2026-08-17", 18, ""),
            ("2026-08-24", 26, ""),
            ("2026-08-31", 35, ""),
            ("2026-09-07", 42, ""),
            ("2026-09-14", 48, ""),
            ("2026-09-21", 52, ""),
            ("2026-09-28", 56, ""),
            ("2026-10-05", 60, ""),
            ("2026-10-07", 61.6, "Hari ini"),
            ("2026-10-12", 66, ""),
            ("2026-10-19", 76, ""),
            ("2026-10-26", 90, ""),
            ("2026-10-30", 100, "Selesai"),
        ])
        self.history(p, {
            "2026-08-03": 0, "2026-08-10": -2, "2026-08-17": -3,
            "2026-08-24": -4, "2026-08-31": -3.5, "2026-09-07": -3,
            "2026-09-14": -3, "2026-09-21": -4, "2026-09-28": -3,
            "2026-10-05": -2.5, "2026-10-07": -2,
        })

        Issue.objects.create(
            project=p, task=t_perf,
            title="Production-like environment belum tersedia",
            description="Env staging tidak merepresentasikan beban produksi.",
            severity=Priority.CRITICAL, priority=Priority.CRITICAL,
            status=IssueStatus.BLOCKED, owner=budi, due_date=D("2026-10-10"),
        )
        Issue.objects.create(
            project=p,
            title="Email delivery rate limited by provider",
            description="Provider email membatasi 100 mail/jam pada plan trial.",
            severity=Priority.HIGH, priority=Priority.HIGH,
            status=IssueStatus.OPEN, owner=andi, due_date=D("2026-10-12"),
        )
        Issue.objects.create(
            project=p, task=t_int,
            title="Approval flow v2 requirement change",
            description="Stakeholder minta approval 2 level (sebelumnya 1 level).",
            severity=Priority.MEDIUM, priority=Priority.MEDIUM,
            status=IssueStatus.IN_PROGRESS, owner=fahril, due_date=D("2026-10-15"),
        )
        resolved = Issue.objects.create(
            project=p,
            title="SSO redirect URI mismatch on staging",
            severity=Priority.HIGH, priority=Priority.HIGH,
            status=IssueStatus.RESOLVED, owner=budi,
            resolution="Update reply URL di Entra app registration.",
        )
        Issue.objects.filter(pk=resolved.pk).update(
            resolved_at=timezone.now() - timedelta(days=1)
        )

        note = Note.objects.create(
            project=p, title="Weekly Sync — Oct 5", author=fahril,
            tags="meeting,sync",
            content=(
                "- Scheduler engine selesai 70%, target finish Oct 10\n"
                "- Notification API di-pickup Andi\n"
                "- Performance testing menunggu env (blocked, ada issue critical)\n"
                "- UAT start digeser ke Oct 26"
            ),
        )
        Note.objects.filter(pk=note.pk).update(
            created_at=timezone.now() - timedelta(days=2),
            updated_at=timezone.now() - timedelta(days=2),
        )
        note2 = Note.objects.create(
            project=p, title="UAT Entry Criteria", author=fahril, tags="uat,checklist",
            content=(
                "1. Integration testing selesai, 0 critical bug\n"
                "2. Performance test lulus threshold 2 rps\n"
                "3. User master & dokumentasi siap\n"
                "4. Sign-off requirement dari HR"
            ),
        )
        Note.objects.filter(pk=note2.pk).update(
            created_at=timezone.now() - timedelta(days=1),
            updated_at=timezone.now() - timedelta(days=1),
        )

        dec = Decision.objects.create(
            project=p, title="Quota pakai Redis",
            decision="Gunakan Redis untuk quota management.",
            context="Notification sender bisa burst ribuan request per menit.",
            reason="Reduce database load during high traffic.",
            impact="Tambahan 1 service cache; monitoring terpisah.",
            decision_maker=budi,
        )
        Decision.objects.filter(pk=dec.pk).update(
            created_at=timezone.now() - timedelta(days=19)
        )
        dec2 = Decision.objects.create(
            project=p, title="Phased rollout VMS notification",
            decision="Rollout notification per batch 200 user.",
            context="Provider email trial membatasi throughput.",
            reason="Hindari bounce rate tinggi & kena limit provider.",
            decision_maker=fahril,
        )
        Decision.objects.filter(pk=dec2.pk).update(
            created_at=timezone.now() - timedelta(days=7)
        )

        self.activity(p, fahril, ActivityAction.TASK_UPDATED,
                      'Fahril updated task "Scheduler Engine"', timedelta(hours=2))
        self.activity(p, andi, ActivityAction.TASK_STATUS,
                      'Andi changed status of "Reporting Module" to Review',
                      timedelta(hours=5))
        self.activity(p, budi, ActivityAction.ISSUE_RESOLVED,
                      'Budi resolved issue "SSO redirect URI mismatch on staging"',
                      timedelta(days=1, hours=3))
        self.activity(p, fahril, ActivityAction.NOTE_ADDED,
                      'Note "UAT Entry Criteria" added', timedelta(days=1, hours=6))
        self.activity(p, fahril, ActivityAction.MILESTONE_COMPLETED,
                      'Milestone "Core Development Complete" completed',
                      timedelta(days=5))
        self.activity(p, fahril, ActivityAction.TIMELINE_CHANGED,
                      "PM changed project timeline", timedelta(days=3))
        self.activity(p, andi, ActivityAction.ISSUE_CREATED,
                      'Issue "Email delivery rate limited by provider" created',
                      timedelta(days=6))
        self.activity(p, fahril, ActivityAction.PROGRESS_UPDATED,
                      "Progress updated to 59.50%", timedelta(days=2, hours=4))

    # ------------------------------------------------------- project lain ---

    def _lbr(self, andi, budi, sari):
        p = Project.objects.create(
            code="LBR-02", name="Ledger Bridge Reconciliation",
            description="Rekonsiliasi invoice WHMCS ↔ Duitku + monitoring mutasi bank.",
            manager=andi, team="Finance",
            start_date=D("2026-09-15"), target_end_date=D("2026-12-15"),
            status=ProjectStatus.ON_TRACK,
        )
        ph1 = Phase.objects.create(project=p, sequence=1, name="Discovery",
                                   start_date=D("2026-09-15"), end_date=D("2026-09-30"),
                                   status=PhaseStatus.COMPLETED)
        ph2 = Phase.objects.create(project=p, sequence=2, name="Build",
                                   start_date=D("2026-10-01"), end_date=D("2026-11-30"),
                                   status=PhaseStatus.IN_PROGRESS)
        p.current_phase = ph2
        p.save(update_fields=["current_phase"])
        Milestone.objects.create(project=p, name="Sync Engine Ready",
                                 date=D("2026-10-30"), status=MilestoneStatus.UPCOMING,
                                 owner=andi)
        Milestone.objects.create(project=p, name="Go-live", date=D("2026-12-15"),
                                 status=MilestoneStatus.UPCOMING, owner=andi)

        self.task(p, title="WHMCS Invoice Mapping", phase=ph1, weight=10,
                  status=TaskStatus.DONE, progress=100, assignee=andi,
                  dates=("2026-09-15", "2026-09-25"))
        self.task(p, title="Duitku Transaction Sync", phase=ph1, weight=10,
                  status=TaskStatus.DONE, progress=100, assignee=andi,
                  dates=("2026-09-20", "2026-09-30"))
        self.task(p, title="Matching Engine", phase=ph2, weight=15,
                  status=TaskStatus.IN_PROGRESS, progress=45, assignee=budi,
                  dates=("2026-10-01", "2026-11-10"), order=1)
        self.task(p, title="Bank Statement Import", phase=ph2, weight=15,
                  status=TaskStatus.IN_PROGRESS, progress=30, assignee=budi,
                  dates=("2026-10-05", "2026-11-15"), order=2)
        self.task(p, title="Recon Report", phase=ph2, weight=25,
                  status=TaskStatus.BACKLOG, progress=0, assignee=sari,
                  dates=("2026-11-01", "2026-11-25"), order=3)
        self.task(p, title="Go-live Checklist", phase=ph2, weight=25,
                  status=TaskStatus.BACKLOG, progress=0, assignee=sari,
                  dates=("2026-11-20", "2026-12-10"), order=4)

        self.baseline(p, [
            ("2026-09-15", 0, "Start"),
            ("2026-09-22", 8, ""),
            ("2026-09-29", 18, ""),
            ("2026-10-06", 29, ""),
            ("2026-10-07", 30, "Hari ini"),
            ("2026-10-31", 60, ""),
            ("2026-12-15", 100, "Selesai"),
        ])
        self.history(p, {
            "2026-09-15": 0, "2026-09-22": 1, "2026-09-29": 2,
            "2026-10-06": 1.5, "2026-10-07": 1.25,
        })
        Issue.objects.create(
            project=p, title="WHMCS webhook retries drop on timeout",
            severity=Priority.LOW, priority=Priority.LOW,
            status=IssueStatus.OPEN, owner=andi, due_date=D("2026-10-20"),
        )
        note = Note.objects.create(project=p, title="Kickoff Notes — Sep 15",
                                   author=andi, tags="meeting",
                                   content="Scope: recon invoice + saldo dashboard. "
                                           "Out of scope: transfer (read-only).")
        Note.objects.filter(pk=note.pk).update(
            created_at=timezone.now() - timedelta(days=22),
            updated_at=timezone.now() - timedelta(days=22),
        )

    def _cp(self, budi, sari, andi):
        p = Project.objects.create(
            code="CP-03", name="Customer Portal Revamp",
            description="Redesign portal customer: login, order history, pembayaran.",
            manager=budi, team="Frontend",
            start_date=D("2026-08-01"), target_end_date=D("2026-10-05"),
            status=ProjectStatus.DELAYED,
        )
        ph1 = Phase.objects.create(project=p, sequence=1, name="Design",
                                   start_date=D("2026-08-01"), end_date=D("2026-08-29"),
                                   status=PhaseStatus.COMPLETED)
        ph2 = Phase.objects.create(project=p, sequence=2, name="Build",
                                   start_date=D("2026-09-01"), end_date=D("2026-10-05"),
                                   status=PhaseStatus.IN_PROGRESS)
        p.current_phase = ph2
        p.save(update_fields=["current_phase"])
        Milestone.objects.create(project=p, name="Beta Release", date=D("2026-09-15"),
                                 status=MilestoneStatus.DELAYED, owner=budi)
        Milestone.objects.create(project=p, name="Public Launch", date=D("2026-10-05"),
                                 status=MilestoneStatus.DELAYED, owner=budi)

        self.task(p, title="Portal Design System", phase=ph1, weight=10,
                  status=TaskStatus.DONE, progress=100, assignee=sari,
                  dates=("2026-08-01", "2026-08-20"))
        self.task(p, title="Login & Profile Page", phase=ph1, weight=10,
                  status=TaskStatus.DONE, progress=100, assignee=sari,
                  dates=("2026-08-18", "2026-08-29"))
        pay = self.task(p, title="Payment Integration", phase=ph2, weight=10,
                        status=TaskStatus.BLOCKED, progress=0, assignee=andi,
                        dates=("2026-09-01", "2026-09-30"), order=1,
                        blocked_reason="Sandbox payment provider belum aktif.",
                        blocked_dependency="Vendor")
        self.task(p, title="Order History Page", phase=ph2, weight=10,
                  status=TaskStatus.IN_PROGRESS, progress=50, assignee=budi,
                  dates=("2026-09-08", "2026-10-02"), order=2)
        self.task(p, title="Notification Center", phase=ph2, weight=10,
                  status=TaskStatus.TODO, progress=0, assignee=sari,
                  dates=("2026-09-22", "2026-10-03"), order=3)
        self.task(p, title="Performance Optimization", phase=ph2, weight=10,
                  status=TaskStatus.BACKLOG, progress=0, assignee=budi,
                  dates=("2026-10-01", "2026-10-05"), order=4)

        self.baseline(p, [
            ("2026-08-01", 0, "Start"),
            ("2026-08-15", 20, ""),
            ("2026-09-01", 45, ""),
            ("2026-09-15", 70, ""),
            ("2026-09-30", 90, ""),
            ("2026-10-05", 100, "Target"),
        ])
        self.history(p, {
            "2026-08-01": 0, "2026-08-15": -8, "2026-09-01": -18,
            "2026-09-15": -26, "2026-09-30": -34, "2026-10-05": -40,
            "2026-10-07": -40,
        })
        Issue.objects.create(
            project=p, task=pay,
            title="Payment provider sandbox belum aktif",
            description="Menunggu aktivasi sandbox dari provider (SLA 10 hari kerja).",
            severity=Priority.CRITICAL, priority=Priority.CRITICAL,
            status=IssueStatus.OPEN, owner=andi, due_date=D("2026-10-10"),
        )

    def _dwm(self, fahril, budi, sari):
        p = Project.objects.create(
            code="DWM-04", name="Data Warehouse Migration",
            description="Migrasi warehouse lama ke setup baru + validasi data.",
            manager=fahril, team="Data",
            start_date=D("2026-06-01"), target_end_date=D("2026-09-15"),
            actual_end_date=D("2026-09-15"), status=ProjectStatus.COMPLETED,
        )
        ph1 = Phase.objects.create(project=p, sequence=1, name="Migration",
                                   start_date=D("2026-06-01"), end_date=D("2026-09-12"),
                                   status=PhaseStatus.COMPLETED)
        ph2 = Phase.objects.create(project=p, sequence=2, name="Handover",
                                   start_date=D("2026-09-13"), end_date=D("2026-09-15"),
                                   status=PhaseStatus.COMPLETED)
        p.current_phase = ph2
        p.save(update_fields=["current_phase"])
        Milestone.objects.create(project=p, name="Migration Cutover",
                                 date=D("2026-09-12"),
                                 status=MilestoneStatus.COMPLETED, owner=fahril)
        Milestone.objects.create(project=p, name="Handover", date=D("2026-09-15"),
                                 status=MilestoneStatus.COMPLETED, owner=fahril)

        for title, weight, assignee in [
            ("Source System Audit", 10, fahril),
            ("ETL Pipeline Build", 25, budi),
            ("Schema Migration", 25, budi),
            ("Data Validation", 20, sari),
            ("Cutover", 20, fahril),
        ]:
            self.task(p, title=title, phase=ph1, weight=weight,
                      status=TaskStatus.DONE, progress=100, assignee=assignee,
                      dates=("2026-06-01", "2026-09-10"))

        self.baseline(p, [
            ("2026-06-01", 0, "Start"),
            ("2026-07-01", 35, ""),
            ("2026-08-01", 70, ""),
            ("2026-09-01", 95, ""),
            ("2026-09-15", 100, "Selesai"),
        ])
        self.history(p, {
            "2026-06-01": 0, "2026-07-01": -2, "2026-08-01": -1,
            "2026-09-01": 0, "2026-09-15": 0, "2026-10-07": 0,
        })

    def _soc(self, andi):
        Project.objects.create(
            code="SOC-05", name="SOC Monitoring Dashboard",
            description="Dashboard monitoring SOC — masih tahap planning.",
            manager=andi, team="Infrastructure",
            start_date=D("2026-11-02"), target_end_date=D("2026-12-20"),
            status=ProjectStatus.PLANNING,
        )

    def _apg(self, budi, sari, andi):
        p = Project.objects.create(
            code="APG-06", name="API Gateway Migration",
            description="Migrasi service lama ke API gateway terpusat.",
            manager=budi, team="Platform",
            start_date=D("2026-09-01"), target_end_date=D("2026-11-30"),
            status=ProjectStatus.ON_TRACK,
        )
        ph1 = Phase.objects.create(project=p, sequence=1, name="Foundation",
                                   start_date=D("2026-09-01"), end_date=D("2026-10-16"),
                                   status=PhaseStatus.IN_PROGRESS)
        ph2 = Phase.objects.create(project=p, sequence=2, name="Migration",
                                   start_date=D("2026-10-19"), end_date=D("2026-11-21"),
                                   status=PhaseStatus.NOT_STARTED)
        _ph3 = Phase.objects.create(project=p, sequence=3, name="Stabilize",
                                   start_date=D("2026-11-23"), end_date=D("2026-11-30"),
                                   status=PhaseStatus.NOT_STARTED)
        p.current_phase = ph1
        p.save(update_fields=["current_phase"])
        Milestone.objects.create(project=p, name="Gateway Ready",
                                 date=D("2026-10-16"), status=MilestoneStatus.UPCOMING,
                                 owner=budi)

        self.task(p, title="Gateway Setup", phase=ph1, weight=20,
                  status=TaskStatus.DONE, progress=100, assignee=budi,
                  dates=("2026-09-01", "2026-09-19"))
        self.task(p, title="Route Migration", phase=ph1, weight=20,
                  status=TaskStatus.IN_PROGRESS, progress=60, assignee=budi,
                  dates=("2026-09-22", "2026-10-16"), order=1)
        self.task(p, title="Service Auth", phase=ph1, weight=20,
                  status=TaskStatus.IN_PROGRESS, progress=30, assignee=andi,
                  dates=("2026-10-01", "2026-10-16"), order=2)
        self.task(p, title="Load Test", phase=ph2, weight=20,
                  status=TaskStatus.TODO, progress=0, assignee=sari,
                  dates=("2026-10-19", "2026-11-07"), order=3)
        self.task(p, title="Rollback Plan", phase=ph2, weight=20,
                  status=TaskStatus.BACKLOG, progress=0, assignee=budi,
                  dates=("2026-10-19", "2026-11-14"), order=4)

        self.baseline(p, [
            ("2026-09-01", 0, "Start"),
            ("2026-09-15", 18, ""),
            ("2026-09-30", 34, ""),
            ("2026-10-07", 36, "Hari ini"),
            ("2026-10-31", 65, ""),
            ("2026-11-30", 100, "Selesai"),
        ])
        self.history(p, {
            "2026-09-01": 0, "2026-09-15": 2, "2026-09-30": 3,
            "2026-10-06": 2, "2026-10-07": 2,
        })

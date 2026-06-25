from io import StringIO
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from pathlib import Path
from datetime import datetime, timedelta
import csv

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_REJECTED,
    ANNOTATION_STATUS_SUBMITTED,
    PROFILE_ROLE_ADMIN,
    SCORE_KIND_AWARD,
)
from .forms import AnnotationForm
from .maintenance import read_maintenance_state
from .models import Annotation, ScoreEvent, SourceRecord
from .views import records_available_for_user


class HealthAndMaintenanceTests(TestCase):
    def test_healthz_reports_ok(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "ok")
        self.assertFalse(payload["maintenance"])

    def test_maintenance_mode_returns_service_page_and_keeps_healthz_open(self):
        with TemporaryDirectory() as tmp, override_settings(MAINTENANCE_MODE_FILE=Path(tmp) / "maintenance.json"):
            call_command("maintenance", "on", "--eta", "15 минут", stdout=StringIO())

            page = self.client.get(reverse("login"))
            health = self.client.get(reverse("healthz"))

            self.assertEqual(page.status_code, 503)
            self.assertContains(page, "Сервис временно на обслуживании", status_code=503)
            self.assertContains(page, "15 минут", status_code=503)
            self.assertEqual(page["Retry-After"], "900")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["maintenance"])

    def test_maintenance_command_disables_mode(self):
        with TemporaryDirectory() as tmp, override_settings(MAINTENANCE_MODE_FILE=Path(tmp) / "maintenance.json"):
            call_command("maintenance", "on", stdout=StringIO())
            call_command("maintenance", "off", stdout=StringIO())

            response = self.client.get(reverse("login"))

            self.assertEqual(response.status_code, 200)

    def test_maintenance_mode_supports_countdown_duration(self):
        with TemporaryDirectory() as tmp, override_settings(MAINTENANCE_MODE_FILE=Path(tmp) / "maintenance.json"):
            started_at = timezone.now()
            out = StringIO()

            call_command("maintenance", "on", "--duration", "20m", stdout=out)

            state = read_maintenance_state()
            ends_at = datetime.fromisoformat(state["ends_at"])
            page = self.client.get(reverse("login"))

            self.assertGreaterEqual(ends_at, started_at + timedelta(minutes=19, seconds=50))
            self.assertLessEqual(ends_at, started_at + timedelta(minutes=20, seconds=10))
            self.assertContains(page, "data-countdown", status_code=503)
            self.assertContains(page, "data-ends-at", status_code=503)
            self.assertIn("Ends at:", out.getvalue())


class AnnotationAccessTests(TestCase):
    def setUp(self):
        self.record = SourceRecord.objects.create(
            text="В подъезде не работает лифт уже неделю.",
            post_text="Жители дома жалуются на обслуживание управляющей компании.",
            source_hash=SourceRecord.build_hash("В подъезде не работает лифт уже неделю."),
        )

    def create_user(self, username, role="student", approved=True):
        user = User.objects.create_user(username=username, password="StrongPass123")
        user.profile.role = role
        user.profile.is_approved = approved
        user.profile.save(update_fields=["role", "is_approved"])
        return user

    def create_record(self, text):
        return SourceRecord.objects.create(text=text, source_hash=SourceRecord.build_hash(text))

    def test_unapproved_user_is_sent_to_pending_page(self):
        user = self.create_user("student1", approved=False)
        client = Client()
        client.login(username=user.username, password="StrongPass123")

        response = client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("pending_approval"), response["Location"])

    def test_approved_student_can_submit_annotation(self):
        user = self.create_user("student2")
        client = Client()
        client.login(username=user.username, password="StrongPass123")

        response = client.post(
            reverse("annotate_record", args=[self.record.id]),
            {
                "jkh_relevance": "yes",
                "jkh_topic": "house_common_property",
                "authority_aspect": "poor_quality",
                "sentiment": "negative",
                "appeal_type": "complaint",
                "responsible_party": "management_company",
                "sarcasm": "no",
                "quality": "normal",
                "student_comment": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation = Annotation.objects.get(student=user, record=self.record)
        self.assertEqual(annotation.status, ANNOTATION_STATUS_SUBMITTED)

    def test_non_jkh_submission_forces_non_applicable_dependent_fields(self):
        user = self.create_user("student_no_jkh")
        client = Client()
        client.login(username=user.username, password="StrongPass123")

        response = client.post(
            reverse("annotate_record", args=[self.record.id]),
            {
                "jkh_relevance": "no",
                "jkh_topic": "public_authorities",
                "authority_aspect": "poor_quality",
                "sentiment": "negative",
                "appeal_type": "complaint",
                "responsible_party": "local_administration",
                "sarcasm": "no",
                "quality": "normal",
                "student_comment": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation = Annotation.objects.get(student=user, record=self.record)
        self.assertEqual(annotation.jkh_topic, "not_jkh")
        self.assertEqual(annotation.authority_aspect, "not_applicable")
        self.assertEqual(annotation.responsible_party, "not_applicable")

    def test_jkh_submission_requires_dependent_fields(self):
        form = AnnotationForm(
            {
                "jkh_relevance": "yes",
                "jkh_topic": "",
                "authority_aspect": "",
                "sentiment": "negative",
                "appeal_type": "complaint",
                "responsible_party": "",
                "sarcasm": "no",
                "quality": "normal",
                "student_comment": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("jkh_topic", form.errors)
        self.assertIn("authority_aspect", form.errors)
        self.assertIn("responsible_party", form.errors)

    def test_annotation_admin_can_reject_and_assign_penalty(self):
        student = self.create_user("student3")
        admin = self.create_user("reviewer", role=PROFILE_ROLE_ADMIN)
        annotation = Annotation.objects.create(
            record=self.record,
            student=student,
            jkh_relevance="yes",
            jkh_topic="house_common_property",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="management_company",
            sarcasm="no",
            quality="normal",
        )
        client = Client()
        client.login(username=admin.username, password="StrongPass123")

        response = client.post(
            reverse("review_annotation", args=[annotation.id]),
            {
                "decision": ANNOTATION_STATUS_REJECTED,
                "award_points": 0,
                "penalty_points": 2,
                "review_comment": "Неверная тема.",
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.assertEqual(annotation.status, ANNOTATION_STATUS_REJECTED)
        self.assertEqual(ScoreEvent.objects.get(student=student).points, -2)

    def test_annotation_admin_can_approve_pending_student(self):
        pending = self.create_user("student4", approved=False)
        admin = self.create_user("reviewer2", role=PROFILE_ROLE_ADMIN)
        client = Client()
        client.login(username=admin.username, password="StrongPass123")

        page = client.get(reverse("participant_list"))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, pending.username)

        response = client.post(reverse("approve_participant", args=[pending.profile.id]))

        self.assertEqual(response.status_code, 302)
        pending.profile.refresh_from_db()
        self.assertTrue(pending.profile.is_approved)
        self.assertEqual(pending.profile.approved_by, admin)

    def test_regular_student_cannot_open_participant_list(self):
        student = self.create_user("student5")
        client = Client()
        client.login(username=student.username, password="StrongPass123")

        response = client.get(reverse("participant_list"))

        self.assertEqual(response.status_code, 403)

    def test_annotate_next_reserves_record_and_skips_it_for_another_student(self):
        second_record = self.create_record("Во дворе не убирают мусор после выходных.")
        first = self.create_user("student6")
        second = self.create_user("student7")
        first_client = Client()
        second_client = Client()
        first_client.login(username=first.username, password="StrongPass123")
        second_client.login(username=second.username, password="StrongPass123")

        first_response = first_client.get(reverse("annotate_next"))

        self.assertEqual(first_response.status_code, 302)
        first_record_id = int(first_response["Location"].rstrip("/").split("/")[-1])
        first_record = SourceRecord.objects.get(id=first_record_id)
        self.assertIn(first_record_id, {self.record.id, second_record.id})
        self.assertEqual(first_record.reserved_by, first)
        self.assertGreater(first_record.reserved_until, timezone.now() + timedelta(minutes=14))

        second_response = second_client.get(reverse("annotate_next"))

        self.assertEqual(second_response.status_code, 302)
        second_record_id = int(second_response["Location"].rstrip("/").split("/")[-1])
        self.assertIn(second_record_id, {self.record.id, second_record.id})
        self.assertNotEqual(first_record_id, second_record_id)

    def test_expired_reservation_can_be_reused_by_another_student(self):
        first = self.create_user("student8")
        second = self.create_user("student9")
        self.record.reserved_by = first
        self.record.reserved_until = timezone.now() - timedelta(minutes=1)
        self.record.save(update_fields=["reserved_by", "reserved_until"])
        client = Client()
        client.login(username=second.username, password="StrongPass123")

        response = client.get(reverse("annotate_next"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("annotate_record", args=[self.record.id]), response["Location"])
        self.record.refresh_from_db()
        self.assertEqual(self.record.reserved_by, second)

    def test_submitted_record_is_not_reissued_to_another_student(self):
        first = self.create_user("student10")
        second = self.create_user("student11")
        Annotation.objects.create(
            record=self.record,
            student=first,
            jkh_relevance="yes",
            jkh_topic="house_common_property",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="management_company",
            sarcasm="no",
            quality="normal",
        )
        client = Client()
        client.login(username=second.username, password="StrongPass123")

        response = client.get(reverse("annotate_next"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "annotation/no_records.html")

    def test_available_records_query_avoids_distinct_for_locked_selection(self):
        student = self.create_user("student_lock_sql")

        query_sql = str(records_available_for_user(student).query).upper()

        self.assertIn("EXISTS", query_sql)
        self.assertNotIn("DISTINCT", query_sql)

    def test_repair_legacy_annotations_normalizes_and_awards_without_penalty(self):
        student = self.create_user("legacy_student")
        reviewer = self.create_user("oldskull")
        legacy_annotation = Annotation.objects.create(
            record=self.record,
            student=student,
            jkh_relevance="no",
            jkh_topic="yard_area",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="local_administration",
            sarcasm="no",
            quality="normal",
        )
        consistent_record = self.create_record("РљРѕРјРјРµРЅС‚Р°СЂРёР№ РЅРµ РїСЂРѕ Р–РљРҐ.")
        consistent_annotation = Annotation.objects.create(
            record=consistent_record,
            student=student,
            jkh_relevance="no",
            jkh_topic="not_jkh",
            authority_aspect="not_applicable",
            sentiment="neutral",
            appeal_type="opinion",
            responsible_party="not_applicable",
            sarcasm="no",
            quality="normal",
        )

        dry_run = StringIO()
        call_command("repair_legacy_annotations", "--reviewer", reviewer.username, stdout=dry_run)
        legacy_annotation.refresh_from_db()
        self.assertEqual(legacy_annotation.status, ANNOTATION_STATUS_SUBMITTED)
        self.assertEqual(ScoreEvent.objects.count(), 0)
        self.assertIn("legacy_annotations=1", dry_run.getvalue())

        call_command("repair_legacy_annotations", "--reviewer", reviewer.username, "--apply", stdout=StringIO())

        legacy_annotation.refresh_from_db()
        consistent_annotation.refresh_from_db()
        self.assertEqual(legacy_annotation.status, ANNOTATION_STATUS_APPROVED)
        self.assertEqual(legacy_annotation.jkh_topic, "not_jkh")
        self.assertEqual(legacy_annotation.authority_aspect, "not_applicable")
        self.assertEqual(legacy_annotation.responsible_party, "not_applicable")
        self.assertEqual(legacy_annotation.reviewed_by, reviewer)
        self.assertEqual(consistent_annotation.status, ANNOTATION_STATUS_SUBMITTED)
        score_event = ScoreEvent.objects.get(annotation=legacy_annotation)
        self.assertEqual(score_event.kind, SCORE_KIND_AWARD)
        self.assertEqual(score_event.points, 1)

    def test_only_oldskull_superuser_gets_project_superadmin_access(self):
        accidental = User.objects.create_superuser("accidental", "a@example.test", "StrongPass123")
        oldskull = User.objects.create_superuser("oldskull", "o@example.test", "StrongPass123")

        accidental_client = Client()
        accidental_client.login(username=accidental.username, password="StrongPass123")
        accidental_response = accidental_client.get(reverse("leaderboard_full"))

        oldskull_client = Client()
        oldskull_client.login(username=oldskull.username, password="StrongPass123")
        oldskull_response = oldskull_client.get(reverse("leaderboard_full"))

        self.assertEqual(accidental_response.status_code, 403)
        self.assertEqual(oldskull_response.status_code, 200)
        self.assertContains(oldskull_response, "Суперадмин")

    def test_quick_review_approve_awards_one_point(self):
        student = self.create_user("student12")
        admin = self.create_user("reviewer3", role=PROFILE_ROLE_ADMIN)
        annotation = Annotation.objects.create(
            record=self.record,
            student=student,
            jkh_relevance="yes",
            jkh_topic="house_common_property",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="management_company",
            sarcasm="no",
            quality="normal",
        )
        client = Client()
        client.login(username=admin.username, password="StrongPass123")

        response = client.post(reverse("quick_review_annotation", args=[annotation.id]), {"action": "approve"})

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.assertEqual(annotation.status, ANNOTATION_STATUS_APPROVED)
        self.assertEqual(ScoreEvent.objects.get(student=student).points, 1)

    def test_quick_review_reject_penalizes_two_points(self):
        student = self.create_user("student13")
        admin = self.create_user("reviewer4", role=PROFILE_ROLE_ADMIN)
        annotation = Annotation.objects.create(
            record=self.record,
            student=student,
            jkh_relevance="yes",
            jkh_topic="house_common_property",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="management_company",
            sarcasm="no",
            quality="normal",
        )
        client = Client()
        client.login(username=admin.username, password="StrongPass123")

        response = client.post(reverse("quick_review_annotation", args=[annotation.id]), {"action": "reject"})

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.assertEqual(annotation.status, ANNOTATION_STATUS_REJECTED)
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_active)
        self.assertEqual(ScoreEvent.objects.get(student=student).points, -2)

    def test_deleted_post_report_confirm_excludes_record_without_score(self):
        student = self.create_user("student14")
        admin = self.create_user("reviewer5", role=PROFILE_ROLE_ADMIN)
        student_client = Client()
        student_client.login(username=student.username, password="StrongPass123")
        student_response = student_client.post(reverse("annotate_record", args=[self.record.id]), {"action": "deleted_post"})

        annotation = Annotation.objects.get(student=student, record=self.record)
        self.assertEqual(student_response.status_code, 302)
        self.assertTrue(annotation.is_deleted_post_report)

        admin_client = Client()
        admin_client.login(username=admin.username, password="StrongPass123")
        response = admin_client.post(
            reverse("quick_review_annotation", args=[annotation.id]),
            {"action": "deleted_confirm"},
        )

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(annotation.status, ANNOTATION_STATUS_APPROVED)
        self.assertFalse(self.record.is_active)
        self.assertEqual(ScoreEvent.objects.filter(student=student).count(), 0)

    def test_deleted_post_placeholder_can_be_confirmed_without_report_flag(self):
        student = self.create_user("student14b")
        admin = self.create_user("reviewer5b", role=PROFILE_ROLE_ADMIN)
        self.record.post_text = "Пост удалён"
        self.record.save(update_fields=["post_text"])
        annotation = Annotation.objects.create(
            record=self.record,
            student=student,
            status=ANNOTATION_STATUS_SUBMITTED,
            is_deleted_post_report=False,
            jkh_relevance="unsure",
            jkh_topic="not_jkh",
            authority_aspect="not_applicable",
            sentiment="neutral",
            appeal_type="info",
            responsible_party="not_applicable",
            sarcasm="unsure",
            quality="no_context",
        )
        client = Client()
        client.login(username=admin.username, password="StrongPass123")

        response = client.post(
            reverse("quick_review_annotation", args=[annotation.id]),
            {"action": "deleted_confirm"},
        )

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(annotation.status, ANNOTATION_STATUS_APPROVED)
        self.assertFalse(self.record.is_active)
        self.assertEqual(ScoreEvent.objects.filter(student=student).count(), 0)

    def test_deleted_post_report_reject_penalizes_one_point(self):
        student = self.create_user("student15")
        admin = self.create_user("reviewer6", role=PROFILE_ROLE_ADMIN)
        annotation = Annotation.objects.create(
            record=self.record,
            student=student,
            status=ANNOTATION_STATUS_SUBMITTED,
            is_deleted_post_report=True,
            jkh_relevance="unsure",
            jkh_topic="not_jkh",
            authority_aspect="not_applicable",
            sentiment="neutral",
            appeal_type="info",
            responsible_party="not_applicable",
            sarcasm="unsure",
            quality="no_context",
        )
        client = Client()
        client.login(username=admin.username, password="StrongPass123")

        response = client.post(
            reverse("quick_review_annotation", args=[annotation.id]),
            {"action": "deleted_reject"},
        )

        self.assertEqual(response.status_code, 302)
        annotation.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(annotation.status, ANNOTATION_STATUS_REJECTED)
        self.assertTrue(self.record.is_active)
        self.assertEqual(ScoreEvent.objects.get(student=student).points, -1)

    def test_project_superadmin_can_add_manual_score_correction(self):
        student = self.create_user("student16")
        oldskull = User.objects.create_superuser("oldskull", "old@example.test", "StrongPass123")
        client = Client()
        client.login(username=oldskull.username, password="StrongPass123")

        response = client.post(
            reverse("adjust_score", args=[student.id]),
            {"points": "5", "reason": "bonus"},
        )

        self.assertEqual(response.status_code, 302)
        event = ScoreEvent.objects.get(student=student)
        self.assertIsNone(event.annotation)
        self.assertEqual(event.points, 5)

    def test_pending_export_and_review_decision_import(self):
        reviewer = self.create_user("oldskull")
        first_student = self.create_user("bulk_student1")
        second_student = self.create_user("bulk_student2")
        second_record = self.create_record("Р’ РґРІРѕСЂРµ РїРѕСЃР»Рµ РґРѕР¶РґСЏ СЃС‚РѕРёС‚ РІРѕРґР°.")
        first_annotation = Annotation.objects.create(
            record=self.record,
            student=first_student,
            jkh_relevance="yes",
            jkh_topic="house_common_property",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="management_company",
            sarcasm="no",
            quality="normal",
        )
        second_annotation = Annotation.objects.create(
            record=second_record,
            student=second_student,
            jkh_relevance="yes",
            jkh_topic="yard_area",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="local_administration",
            sarcasm="no",
            quality="normal",
        )

        with TemporaryDirectory() as tmp:
            export_path = Path(tmp) / "pending.csv"
            decisions_path = Path(tmp) / "decisions.csv"
            export_out = StringIO()

            call_command("export_pending_annotations", str(export_path), stdout=export_out)

            self.assertIn("Exported 2 pending annotations", export_out.getvalue())
            with export_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
                fieldnames = rows[0].keys()
            rows[0]["review_action"] = "approve"
            rows[0]["review_comment"] = "Логично."
            rows[1]["review_action"] = "reject"
            rows[1]["review_comment"] = "Неверно выбрана тема."
            with decisions_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            dry_run = StringIO()
            call_command("apply_review_decisions", str(decisions_path), "--reviewer", reviewer.username, "--dry-run", stdout=dry_run)
            first_annotation.refresh_from_db()
            self.assertEqual(first_annotation.status, ANNOTATION_STATUS_SUBMITTED)
            self.assertEqual(ScoreEvent.objects.count(), 0)
            self.assertIn("decisions=2", dry_run.getvalue())

            call_command("apply_review_decisions", str(decisions_path), "--reviewer", reviewer.username, stdout=StringIO())

        first_annotation.refresh_from_db()
        second_annotation.refresh_from_db()
        self.assertEqual(first_annotation.status, ANNOTATION_STATUS_APPROVED)
        self.assertEqual(second_annotation.status, ANNOTATION_STATUS_REJECTED)
        self.assertEqual(ScoreEvent.objects.get(annotation=first_annotation).points, 1)
        self.assertEqual(ScoreEvent.objects.get(annotation=second_annotation).points, -2)


class BuildReviewContextBundleCommandTests(TestCase):
    def test_exports_all_available_comments_for_pending_post(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pending_path = root / "pending.csv"
            dataset_path = root / "dataset.csv"
            output_dir = root / "context"
            pending_path.write_text(
                "annotation_id,source_url,comment_text\n"
                "41,https://vk.com/wall-1_10?reply=21,Target comment\n"
                "42,https://vk.com/wall-1_10?reply=21,Target comment\n",
                encoding="utf-8-sig",
            )
            dataset_path.write_text(
                "text,post_text,data_type,group_name,post_id,comment_id,comment_url,date,author,file_origin\n"
                "Post text,,post,Group,-1_10,,https://vk.com/wall-1_10,2026-05-01,Owner,raw.csv\n"
                "Earlier reply,Post text,comment,Group,-1_10,20,https://vk.com/wall-1_10?reply=20,2026-05-02,First,raw.csv\n"
                "Target comment,Post text,comment,Group,-1_10,21,https://vk.com/wall-1_10?reply=21,2026-05-03,Second,raw.csv\n"
                '"[id1|Second], Target comment",Post text,comment,Group,-1_10,21,https://vk.com/wall-1_10?reply=21,2026-05-03,Second,parsed.csv\n'
                "Other post,Other post,comment,Group,-1_11,31,https://vk.com/wall-1_11?reply=31,2026-05-03,Third,raw.csv\n",
                encoding="utf-8-sig",
            )

            out = StringIO()
            call_command(
                "build_review_context_bundle",
                str(pending_path),
                str(dataset_path),
                str(output_dir),
                stdout=out,
            )

            with (output_dir / "pending_context_index.csv").open("r", encoding="utf-8-sig", newline="") as f:
                index_rows = list(csv.DictReader(f))
            with (output_dir / "pending_post_comments_context.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as f:
                context_rows = list(csv.DictReader(f))

            self.assertEqual(len(index_rows), 2)
            self.assertEqual(index_rows[0]["context_comment_count"], "2")
            self.assertEqual(index_rows[0]["context_scope"], "all_comments_under_same_post_no_reply_tree")
            self.assertEqual(len(context_rows), 2)
            self.assertEqual(context_rows[1]["is_pending_target"], "True")
            self.assertEqual(context_rows[1]["target_annotation_ids"], "41|42")
            self.assertEqual(context_rows[1]["text"], "[id1|Second], Target comment")
            self.assertEqual(context_rows[1]["variant_count"], "2")
            self.assertIn("no parent/thread links", out.getvalue())


class ImportRecordsCommandTests(TestCase):
    def run_import(self, content, suffix=".csv", *args):
        with NamedTemporaryFile("w", encoding="utf-8-sig", newline="", suffix=suffix, delete=False) as f:
            f.write(content)
            path = f.name

        out = StringIO()
        call_command("import_records", path, *args, stdout=out)
        return out.getvalue()

    def test_imports_normalizaciya_dataset_schema(self):
        output = self.run_import(
            "text,post_text,comment_url,group_name\n"
            '"В подъезде не работает лифт","Жители жалуются на УК",https://vk.com/wall-1_1?reply=2,Дом\n'
        )

        self.assertIn("Imported: 1; skipped: 0", output)
        record = SourceRecord.objects.get()
        self.assertEqual(record.text, "В подъезде не работает лифт")
        self.assertEqual(record.post_text, "Жители жалуются на УК")
        self.assertEqual(record.source_url, "https://vk.com/wall-1_1?reply=2")
        self.assertEqual(record.group_name, "Дом")

    def test_imports_barkov_comment_schema(self):
        output = self.run_import(
            "ID автора;Ссылка на комментарий;Ссылка на пост;Дата и время;Текст комментария;Число лайков к комментарию\n"
            "1;https://vk.com/wall-1_1?reply=2;https://vk.com/wall-1_1;2026-05-18 10:00;Нет горячей воды уже неделю;3\n"
        )

        self.assertIn("Imported: 1; skipped: 0", output)
        record = SourceRecord.objects.get()
        self.assertEqual(record.text, "Нет горячей воды уже неделю")
        self.assertEqual(record.source_url, "https://vk.com/wall-1_1?reply=2")
        self.assertEqual(record.external_id, "https://vk.com/wall-1_1?reply=2")

    def test_imports_barkov_wallpost_schema_with_comma_heavy_media_urls(self):
        output = self.run_import(
            "ССЫЛКА НА ПОСТ;НАЗВАНИЕ ВЛАДЕЛЬЦА;ДАТА ПУБЛИКАЦИИ;ТЕКСТ;ИЛЛЮСТРАЦИИ\n"
            "https://vk.com/wall-1_1;Городские новости;2026-05-18 10:00;Во дворе сломано освещение;https://example.test/img.jpg?as=32x32,48x48,72x72\n"
        )

        self.assertIn("Imported: 1; skipped: 0", output)
        record = SourceRecord.objects.get()
        self.assertEqual(record.text, "Во дворе сломано освещение")
        self.assertEqual(record.source_url, "https://vk.com/wall-1_1")
        self.assertEqual(record.group_name, "Городские новости")

    def test_dry_run_does_not_create_records(self):
        output = self.run_import(
            "ССЫЛКА НА ПОСТ;НАЗВАНИЕ ВЛАДЕЛЬЦА;ДАТА ПУБЛИКАЦИИ;ТЕКСТ\n"
            "https://vk.com/wall-1_1;Городские новости;2026-05-18 10:00;Во дворе сломано освещение\n",
            ".csv",
            "--dry-run",
        )

        self.assertIn("Would import: 1; skipped: 0", output)
        self.assertEqual(SourceRecord.objects.count(), 0)

    def test_can_import_only_comments_with_post_context(self):
        output = self.run_import(
            "text,post_text,data_type,comment_url\n"
            '"Comment with post","Post context",comment,https://vk.com/wall-1_1?reply=2\n'
            '"Comment without post","",comment,https://vk.com/wall-1_2?reply=3\n'
            '"Standalone post","",post,https://vk.com/wall-1_3\n',
            ".csv",
            "--data-type",
            "comment",
            "--require-post-context",
        )

        self.assertIn("Imported: 1; skipped: 2", output)
        record = SourceRecord.objects.get()
        self.assertEqual(record.text, "Comment with post")
        self.assertEqual(record.post_text, "Post context")


class BuildDatasetCommandTests(TestCase):
    def test_builds_combined_dataset_and_restores_post_context(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            output = root / "processed" / "dataset_combined.csv"
            missing = root / "processed" / "missing_post_context.csv"

            (raw_dir / "dataset.csv").write_text(
                "text,post_text,data_type,has_post_context,group_id,group_name,post_id,comment_id,comment_url,date,author,likes,sentiment,appeal_type,addressee,file_origin\n"
                "Старый комментарий без контекста,,comment,False,-1,Дом,-1_10,20,https://vk.com/wall-1_10?reply=20,2025-11-21,Автор,0,,,,old.csv\n",
                encoding="utf-8-sig",
            )
            (raw_dir / "posts_parsed.csv").write_text(
                "post_id,post_url,post_text,group_id,status,parsed_at\n"
                "-1_10,https://vk.com/wall-1_10,Контекст восстановленного поста,-1,ok,2026-03-22 21:56:17\n",
                encoding="utf-8-sig",
            )
            (raw_dir / "vk.barkov.net-wallposts-2026-05-18_06-26-34.csv").write_text(
                "ССЫЛКА НА ПОСТ;НАЗВАНИЕ ВЛАДЕЛЬЦА;ДАТА ПУБЛИКАЦИИ;ТЕКСТ;ИЛЛЮСТРАЦИИ\n"
                "https://vk.com/wall-2_30;Городские новости;2026-05-18 10:00;Пост про отключение воды;https://example.test/img.jpg?as=32x32,48x48,72x72\n",
                encoding="utf-8-sig",
            )
            (raw_dir / "vk.barkov.net-comments-2026-05-18_07-31-45.csv").write_text(
                "ID автора;Ссылка на автора;Имя и фамилия автора;Пол автора;Ссылка на комментарий;Ссылка на пост;Дата и время;Текст комментария;Число лайков к комментарию\n"
                "1;https://vk.com/id1;Житель;Ж;https://vk.com/wall-2_30?reply=31;https://vk.com/wall-2_30;2026-05-18 11:00;Воды нет второй день;5\n",
                encoding="utf-8-sig",
            )

            out = StringIO()
            call_command(
                "build_dataset",
                str(raw_dir),
                "--output",
                str(output),
                "--missing-output",
                str(missing),
                stdout=out,
            )

            self.assertIn("written=3", out.getvalue())
            with output.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["post_text"], "Контекст восстановленного поста")
            self.assertEqual(rows[2]["post_text"], "Пост про отключение воды")

            with missing.open("r", encoding="utf-8-sig", newline="") as f:
                missing_rows = list(csv.DictReader(f))
            self.assertEqual(missing_rows, [])

    def test_builds_old_comment_context_from_comment_url_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            output = root / "processed" / "dataset_combined.csv"
            missing = root / "processed" / "missing_post_context.csv"

            (raw_dir / "posts_parsed.csv").write_text(
                "post_id,post_url,post_text,group_id,status,parsed_at\n"
                "-1_10,https://vk.com/wall-1_10,Контекст поста из отдельного парсинга,-1,ok,2026-03-22 21:56:17\n",
                encoding="utf-8-sig",
            )
            (raw_dir / "vk.barkov.net-comments-2025-11-21_19-37-54.csv").write_text(
                "ID автора;Ссылка на автора;Имя и фамилия автора;Пол автора;Аватара автора;Ссылка на комментарий;Дата и время;Текст комментария;Число лайков к комментарию\n"
                "1;https://vk.com/id1;Житель;Ж;https://example.test/avatar.jpg;https://vk.com/wall-1_10?reply=20;2025-11-21 13:43;Старый комментарий без отдельной ссылки на пост;1\n",
                encoding="utf-8-sig",
            )

            out = StringIO()
            call_command(
                "build_dataset",
                str(raw_dir),
                "--output",
                str(output),
                "--missing-output",
                str(missing),
                stdout=out,
            )

            self.assertIn("missing_context=0", out.getvalue())
            with output.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["post_id"], "-1_10")
            self.assertEqual(rows[0]["post_text"], "Контекст поста из отдельного парсинга")

    def test_build_dataset_reports_missing_comment_context(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            output = root / "processed" / "dataset_combined.csv"
            missing = root / "processed" / "missing_post_context.csv"

            (raw_dir / "vk.barkov.net-comments-2026-05-18_07-31-45.csv").write_text(
                "ID автора;Ссылка на комментарий;Ссылка на пост;Дата и время;Текст комментария;Число лайков к комментарию\n"
                "1;https://vk.com/wall-9_99?reply=100;https://vk.com/wall-9_99;2026-05-18 11:00;Где контекст поста?;0\n",
                encoding="utf-8-sig",
            )

            out = StringIO()
            call_command(
                "build_dataset",
                str(raw_dir),
                "--output",
                str(output),
                "--missing-output",
                str(missing),
                stdout=out,
            )

            self.assertIn("missing_context=1", out.getvalue())
            with missing.open("r", encoding="utf-8-sig", newline="") as f:
                missing_rows = list(csv.DictReader(f))
            self.assertEqual(len(missing_rows), 1)
            self.assertEqual(missing_rows[0]["post_url"], "https://vk.com/wall-9_99")

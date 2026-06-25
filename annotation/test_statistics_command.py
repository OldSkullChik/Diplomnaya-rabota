import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_REJECTED,
    ANNOTATION_STATUS_SUBMITTED,
    SCORE_KIND_AWARD,
    SCORE_KIND_PENALTY,
)
from .models import Annotation, ScoreEvent, SourceRecord


class ExportAnnotationStatisticsTests(TestCase):
    def create_record(self, text, active=True):
        return SourceRecord.objects.create(
            text=text,
            post_text="Context",
            source_hash=SourceRecord.build_hash(text, "Context"),
            is_active=active,
        )

    def create_annotation(self, record, student, status, deleted=False):
        return Annotation.objects.create(
            record=record,
            student=student,
            status=status,
            is_deleted_post_report=deleted,
            jkh_relevance="yes",
            jkh_topic="yard_area",
            authority_aspect="poor_quality",
            sentiment="negative",
            appeal_type="complaint",
            responsible_party="local_administration",
            sarcasm="no",
            quality="normal",
            reviewed_by=self.reviewer if status != ANNOTATION_STATUS_SUBMITTED else None,
        )

    def setUp(self):
        self.reviewer = User.objects.create_user("reviewer")
        self.student = User.objects.create_user("student", first_name="Test", last_name="Student")

    def test_exports_cumulative_counts_and_infographic(self):
        accepted = self.create_annotation(
            self.create_record("accepted"),
            self.student,
            ANNOTATION_STATUS_APPROVED,
        )
        rejected = self.create_annotation(
            self.create_record("rejected"),
            self.student,
            ANNOTATION_STATUS_REJECTED,
        )
        self.create_annotation(
            self.create_record("deleted", active=False),
            self.student,
            ANNOTATION_STATUS_APPROVED,
            deleted=True,
        )
        self.create_annotation(
            self.create_record("pending"),
            self.student,
            ANNOTATION_STATUS_SUBMITTED,
        )
        ScoreEvent.objects.create(
            student=self.student,
            annotation=accepted,
            created_by=self.reviewer,
            kind=SCORE_KIND_AWARD,
            points=1,
        )
        ScoreEvent.objects.create(
            student=self.student,
            annotation=rejected,
            created_by=self.reviewer,
            kind=SCORE_KIND_PENALTY,
            points=-2,
        )
        ScoreEvent.objects.create(
            student=self.student,
            annotation=None,
            created_by=self.reviewer,
            kind=SCORE_KIND_AWARD,
            points=3,
            reason="Correction",
        )

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "statistics"
            call_command("export_annotation_statistics", str(output_dir), stdout=StringIO())
            payload = json.loads((output_dir / "annotation_statistics.json").read_text(encoding="utf-8"))

            self.assertEqual(payload["totals"]["annotations_submitted_all_time"], 4)
            self.assertEqual(payload["totals"]["annotations_checked"], 3)
            self.assertEqual(payload["totals"]["annotations_approved_dataset"], 1)
            self.assertEqual(payload["totals"]["deleted_posts_confirmed"], 1)
            self.assertEqual(payload["totals"]["annotations_rejected_total"], 1)
            self.assertEqual(payload["totals"]["annotations_pending"], 1)
            self.assertEqual(payload["scores"]["net_points"], 2)
            self.assertTrue((output_dir / "annotation_statistics.md").exists())
            self.assertTrue((output_dir / "participants.csv").exists())
            self.assertTrue((output_dir / "annotation_statistics_infographic.svg").exists())

            dashboard_path = output_dir / "annotation_dashboard_full.svg"
            call_command(
                "render_statistics_dashboard",
                str(output_dir / "annotation_statistics.json"),
                str(dashboard_path),
                stdout=StringIO(),
            )
            dashboard = dashboard_path.read_text(encoding="utf-8")
            self.assertIn("Статистика разметки обращений по ЖКХ", dashboard)
            self.assertIn("Топ-10 участников по баллам", dashboard)

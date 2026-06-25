import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .choices import SAMPLING_POOL_GENERAL, SAMPLING_POOL_JKH_CANDIDATE
from .models import Annotation, ScoreEvent, SourceRecord


class OfflineRecordLabelCommandTests(TestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user("oldskull")
        self.record = SourceRecord.objects.create(
            text="Need heating",
            post_text="Heating is broken in the apartment building.",
            source_hash=SourceRecord.build_hash("Need heating", "Heating is broken in the apartment building."),
            sampling_pool=SAMPLING_POOL_JKH_CANDIDATE,
            jkh_candidate_score=10,
            jkh_candidate_reason="test",
        )
        SourceRecord.objects.create(
            text="General",
            post_text="General news",
            source_hash=SourceRecord.build_hash("General", "General news"),
            sampling_pool=SAMPLING_POOL_GENERAL,
        )

    def test_exports_unresolved_jkh_candidates(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "records.csv"
            call_command("export_unresolved_records", str(output), stdout=StringIO())
            rows = list(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], str(self.record.id))
        self.assertEqual(rows[0]["offline_action"], "")

    def test_applies_offline_label_without_score_event(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "offline_action",
                        "jkh_relevance",
                        "jkh_topic",
                        "authority_aspect",
                        "sentiment",
                        "appeal_type",
                        "responsible_party",
                        "sarcasm",
                        "quality",
                        "offline_comment",
                        "record_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "offline_action": "approve",
                        "jkh_relevance": "yes",
                        "jkh_topic": "heating_hot_water",
                        "authority_aspect": "no_action",
                        "sentiment": "negative",
                        "appeal_type": "complaint",
                        "responsible_party": "resource_provider",
                        "sarcasm": "no",
                        "quality": "normal",
                        "offline_comment": "offline ok",
                        "record_id": self.record.id,
                    }
                )

            call_command(
                "apply_offline_record_labels",
                str(path),
                "--reviewer",
                "oldskull",
                "--create-student",
                stdout=StringIO(),
            )

        annotation = Annotation.objects.get(record=self.record)
        self.assertEqual(annotation.status, "approved")
        self.assertEqual(annotation.student.username, "offline_teacher")
        self.assertEqual(annotation.reviewed_by, self.reviewer)
        self.assertEqual(annotation.jkh_topic, "heating_hot_water")
        self.assertEqual(annotation.score_events.count(), 0)

    def test_can_award_points_to_selected_student(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "offline_action",
                        "jkh_relevance",
                        "jkh_topic",
                        "authority_aspect",
                        "sentiment",
                        "appeal_type",
                        "responsible_party",
                        "sarcasm",
                        "quality",
                        "offline_comment",
                        "record_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "offline_action": "approve",
                        "jkh_relevance": "yes",
                        "jkh_topic": "heating_hot_water",
                        "authority_aspect": "no_action",
                        "sentiment": "negative",
                        "appeal_type": "complaint",
                        "responsible_party": "resource_provider",
                        "sarcasm": "no",
                        "quality": "normal",
                        "offline_comment": "offline ok",
                        "record_id": self.record.id,
                    }
                )

            call_command(
                "apply_offline_record_labels",
                str(path),
                "--reviewer",
                "oldskull",
                "--student",
                "oldskull",
                "--award-points",
                stdout=StringIO(),
            )

        annotation = Annotation.objects.get(record=self.record)
        score = ScoreEvent.objects.get(annotation=annotation)
        self.assertEqual(annotation.student.username, "oldskull")
        self.assertEqual(score.student.username, "oldskull")
        self.assertEqual(score.created_by, self.reviewer)
        self.assertEqual(score.points, 1)

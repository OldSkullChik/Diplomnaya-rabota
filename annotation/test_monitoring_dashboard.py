from django.test import TestCase
from django.utils import timezone

from annotation.models import (
    MonitoringItem,
    MonitoringRun,
    MonitoringSource,
    OmsuArea,
    OmsuDashboardSnapshot,
    OmsuLatestComment,
)
from annotation.monitoring.dashboard import refresh_dashboard_from_monitoring


class MonitoringDashboardRefreshTests(TestCase):
    def test_dashboard_uses_only_jkh_relevant_monitoring_items(self):
        area = OmsuArea.objects.create(slug="sarov", name="Sarov")
        source = MonitoringSource.objects.create(
            slug="sarov-test",
            area=area,
            title="Sarov test",
            url="https://m.vk.com/sarov-test",
            screen_name="sarov-test",
        )
        run = MonitoringRun.objects.create(status=MonitoringRun.STATUS_SUCCESS)
        now = timezone.now()

        MonitoringItem.objects.create(
            source=source,
            run=run,
            area=area,
            item_type=MonitoringItem.ITEM_POST,
            external_id="post-1",
            source_hash=MonitoringItem.build_hash("https://m.vk.com/wall-1_1", "post-1", "trash", ""),
            source_url="https://m.vk.com/wall-1_1",
            text="Resident Name\nвчера в 23:35\nTrash complaint\n1\nПоказать все комментарии",
            author_name="Resident Name",
            published_at=now,
            taxonomy={"jkh_relevance": "yes", "jkh_topic": "waste_cleaning", "sentiment": "negative"},
            omsu_score=-80,
            omsu_negative_probability=0.79,
            omsu_decision="negative_omsu",
            analyzed_at=now,
        )
        MonitoringItem.objects.create(
            source=source,
            run=run,
            area=area,
            item_type=MonitoringItem.ITEM_POST,
            external_id="post-2",
            source_hash=MonitoringItem.build_hash("https://m.vk.com/wall-1_2", "post-2", "job ad", ""),
            source_url="https://m.vk.com/wall-1_2",
            text="Job ad",
            published_at=now,
            taxonomy={"jkh_relevance": "no", "jkh_topic": "not_jkh", "sentiment": "neutral"},
            omsu_score=0,
            omsu_negative_probability=0.02,
            omsu_decision="not_negative_omsu",
            analyzed_at=now,
        )

        result = refresh_dashboard_from_monitoring()

        self.assertEqual(result["snapshots_updated"], 1)
        self.assertEqual(result["latest_comments_created"], 1)
        self.assertEqual(result["items_seen"], 2)
        self.assertEqual(result["items_analyzed"], 2)
        self.assertEqual(result["items_relevant"], 1)

        snapshot = OmsuDashboardSnapshot.objects.get(area=area)
        self.assertEqual(snapshot.omsu_score, -80)
        self.assertEqual(snapshot.comments_total, 1)
        self.assertEqual(snapshot.negative_total, 1)
        self.assertEqual(snapshot.positive_total, 0)
        self.assertEqual(snapshot.top_topics, [{"label": "waste_cleaning", "value": 1}])
        self.assertEqual(snapshot.charts["topic_distribution"], [["waste_cleaning", 1]])
        self.assertEqual(snapshot.charts["sentiment_balance"], [["negative", 1]])
        self.assertIn("chart_catalog", snapshot.charts)
        catalog = {chart["id"]: chart for chart in snapshot.charts["chart_catalog"]}
        self.assertEqual(catalog["score_trend"]["type"], "line")
        self.assertEqual(catalog["sentiment_balance"]["type"], "donut")
        self.assertEqual(catalog["relevance_filter"]["type"], "funnel")
        self.assertEqual(catalog["score_buckets"]["type"], "histogram")
        self.assertEqual(catalog["topic_sentiment_heatmap"]["type"], "heatmap")
        self.assertGreater(catalog["score_trend"]["weight"], catalog["topic_sentiment_heatmap"]["weight"])
        self.assertIn("meaning", catalog["responsible_parties"])
        self.assertIn("android", catalog["responsible_parties"]["client_hints"])
        self.assertEqual(snapshot.charts["chart_layout"]["android_summary"][0], "score_trend")

        latest = OmsuLatestComment.objects.get(area=area)
        self.assertEqual(latest.source_url, "https://m.vk.com/wall-1_1")
        self.assertEqual(latest.text, "Trash complaint")

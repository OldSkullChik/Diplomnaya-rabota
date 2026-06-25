from django.test import TestCase, override_settings
from django.utils import timezone

from .models import OmsuArea, OmsuDashboardSnapshot, OmsuLatestComment


class OmsuApiTests(TestCase):
    def setUp(self):
        self.area = OmsuArea.objects.create(
            slug="test-area",
            name="Тестовый округ",
            area_type="муниципальный округ",
            head_name="Иван Иванов",
            leadership=[{"role": "Глава", "name": "Иван Иванов"}],
            territory_area_km2=123.45,
            population=42000,
            geometry={"type": "Polygon", "coordinates": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        )
        OmsuDashboardSnapshot.objects.create(
            area=self.area,
            omsu_score=-42,
            previous_omsu_score=-25,
            omsu_negative_probability=0.88,
            comments_total=100,
            comments_last_day=12,
            negative_total=60,
            neutral_total=30,
            positive_total=10,
            top_topics=[["Вода", 12]],
            charts={"score_trend": [-25, -30, -42]},
            generated_at=timezone.now(),
        )
        OmsuLatestComment.objects.create(
            area=self.area,
            text="Нет воды третий день, администрация молчит.",
            sentiment="negative",
            omsu_score=-42,
            source_name="test",
        )

    @override_settings(OMSU_API_SNAPSHOT_REFRESH_SECONDS=3600, OMSU_API_COMMENT_REFRESH_SECONDS=5)
    def test_manifest_exposes_refresh_contract(self):
        response = self.client.get("/api/v1/omsu/manifest/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["chart_schema_version"], "2026-06-17")
        self.assertIn("chart_catalog", payload["chart_contract"])
        self.assertEqual(payload["snapshot_refresh_seconds"], 3600)
        self.assertEqual(payload["comment_refresh_seconds"], 5)
        self.assertEqual(payload["refresh_policy"]["snapshot"]["mode"], "after_hourly_monitoring_run")
        self.assertEqual(payload["refresh_policy"]["comments"]["mode"], "poll_latest_comment_endpoint")
        self.assertIn("snapshot", payload["endpoints"])

    def test_snapshot_returns_public_omsu_slice(self):
        response = self.client.get("/api/v1/omsu/snapshot/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("served_at", payload)
        self.assertIn("refresh_policy", payload)
        self.assertEqual(payload["map"]["focus_region"], "Нижегородская область")
        self.assertIn("desktop", payload["widgets"])
        self.assertIn("android", payload["widgets"])
        self.assertIn("topic_sentiment_heatmap", payload["widgets"]["available"])
        self.assertEqual(len(payload["areas"]), 1)
        area = payload["areas"][0]
        self.assertEqual(area["slug"], "test-area")
        self.assertEqual(area["score"], -42)
        self.assertEqual(area["previous_score"], -25)
        self.assertEqual(area["confidence_band"], "high_negative")
        self.assertEqual(area["latest_comment"]["text"], "Нет воды третий день, администрация молчит.")

    def test_area_detail_returns_charts_and_leadership(self):
        response = self.client.get("/api/v1/omsu/areas/test-area/")

        self.assertEqual(response.status_code, 200)
        area = response.json()["area"]
        self.assertEqual(area["head_name"], "Иван Иванов")
        self.assertEqual(area["territory_area_km2"], 123.45)
        self.assertEqual(area["charts"]["score_trend"], [-25, -30, -42])

    def test_latest_comment_can_be_filtered_by_area(self):
        response = self.client.get("/api/v1/omsu/latest-comment/?area=test-area&limit=3")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("served_at", payload)
        self.assertEqual(payload["comment_refresh_seconds"], 5)
        self.assertEqual(len(payload["comments"]), 1)
        comment = payload["comment"]
        self.assertEqual(comment["area_slug"], "test-area")
        self.assertEqual(comment["omsu_score"], -42)

    @override_settings(OMSU_API_REQUIRE_KEY=True, OMSU_API_KEYS=("secret-demo-key",))
    def test_api_rejects_missing_key_when_required(self):
        response = self.client.get("/api/v1/omsu/snapshot/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "invalid_api_key")

    @override_settings(OMSU_API_REQUIRE_KEY=True, OMSU_API_KEYS=("secret-demo-key",))
    def test_api_accepts_x_omsu_api_key_header(self):
        response = self.client.get("/api/v1/omsu/snapshot/", HTTP_X_OMSU_API_KEY="secret-demo-key")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["areas"][0]["slug"], "test-area")

    @override_settings(OMSU_API_REQUIRE_KEY=True, OMSU_API_KEYS=("secret-demo-key",))
    def test_api_accepts_bearer_authorization_header(self):
        response = self.client.get("/api/v1/omsu/manifest/", HTTP_AUTHORIZATION="Bearer secret-demo-key")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["api_version"], "v1")

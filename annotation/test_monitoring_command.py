from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from annotation.management.commands.collect_vk_monitoring_test import Command
from annotation.models import MonitoringSource, OmsuArea


class CollectVkMonitoringCommandTests(TestCase):
    def test_load_sources_prioritizes_never_and_oldest_checked_sources(self):
        area = OmsuArea.objects.create(slug="sarov", name="Sarov")
        recent = MonitoringSource.objects.create(
            slug="recent",
            area=area,
            url="https://vk.com/recent",
            screen_name="recent",
            display_order=1,
            last_success_at=timezone.now(),
        )
        old = MonitoringSource.objects.create(
            slug="old",
            area=area,
            url="https://vk.com/old",
            screen_name="old",
            display_order=2,
            last_success_at=timezone.now() - timedelta(days=2),
        )
        never = MonitoringSource.objects.create(
            slug="never",
            area=area,
            url="https://vk.com/never",
            screen_name="never",
            display_order=3,
        )

        sources = Command().load_sources(
            {
                "source_slugs": [],
                "max_sources": 2,
                "source_shard_count": 1,
                "source_shard_index": 0,
            }
        )

        self.assertEqual([source.slug for source in sources], [never.slug, old.slug])
        self.assertNotIn(recent, sources)

    def test_explicit_source_filter_keeps_display_order(self):
        area = OmsuArea.objects.create(slug="sarov", name="Sarov")
        second = MonitoringSource.objects.create(
            slug="second",
            area=area,
            url="https://vk.com/second",
            screen_name="second",
            display_order=2,
        )
        first = MonitoringSource.objects.create(
            slug="first",
            area=area,
            url="https://vk.com/first",
            screen_name="first",
            display_order=1,
            last_success_at=timezone.now(),
        )

        sources = Command().load_sources(
            {
                "source_slugs": ["second", "first"],
                "max_sources": 0,
                "source_shard_count": 1,
                "source_shard_index": 0,
            }
        )

        self.assertEqual([source.slug for source in sources], [first.slug, second.slug])

    def test_load_sources_can_select_non_overlapping_shards(self):
        area = OmsuArea.objects.create(slug="sarov", name="Sarov")
        for index in range(6):
            MonitoringSource.objects.create(
                slug=f"source-{index}",
                area=area,
                url=f"https://vk.com/source{index}",
                screen_name=f"source{index}",
                display_order=index,
            )

        shard_0 = Command().load_sources(
            {
                "source_slugs": [],
                "max_sources": 0,
                "source_shard_count": 3,
                "source_shard_index": 0,
            }
        )
        shard_1 = Command().load_sources(
            {
                "source_slugs": [],
                "max_sources": 0,
                "source_shard_count": 3,
                "source_shard_index": 1,
            }
        )
        shard_2 = Command().load_sources(
            {
                "source_slugs": [],
                "max_sources": 0,
                "source_shard_count": 3,
                "source_shard_index": 2,
            }
        )

        self.assertEqual([source.slug for source in shard_0], ["source-0", "source-3"])
        self.assertEqual([source.slug for source in shard_1], ["source-1", "source-4"])
        self.assertEqual([source.slug for source in shard_2], ["source-2", "source-5"])

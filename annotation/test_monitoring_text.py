from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from annotation.monitoring.text import clean_ticker_comment_text, clean_vk_text, parse_vk_datetime


class MonitoringTextTests(SimpleTestCase):
    def test_repairs_cp1251_mojibake(self):
        self.assertEqual(clean_vk_text("РђРЅРѕРЅРёРјРЅРѕ. РњСѓСЃРѕСЂ"), "Анонимно. Мусор")

    def test_parses_word_hour_relative_date(self):
        now = timezone.now()
        parsed = parse_vk_datetime("три часа назад", now=now)
        self.assertIsNotNone(parsed)
        self.assertLess(abs((parsed - (now - timedelta(hours=3))).total_seconds()), 2)

    def test_removes_common_vk_service_lines(self):
        cleaned = clean_vk_text("Текст обращения\n1/7\nЛайк\n13\nпросмотров\nГеолокация")
        self.assertEqual(cleaned, "Текст обращения")

    def test_removes_singular_view_counter(self):
        text = "\u0422\u0435\u043a\u0441\u0442\n\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430"
        self.assertEqual(clean_vk_text(text), "\u0422\u0435\u043a\u0441\u0442")

    def test_cleans_ticker_comment_author_dates_and_counters(self):
        text = (
            "\u0421\u0435\u0440\u0451\u0433\u0430 \u0421\u0442\u0435\u043f\u0443\u0448\u0435\u0432\n"
            "\u0432\u0447\u0435\u0440\u0430 \u0432 23:35\n"
            "\u041d\u0435\u0442 \u0432\u043e\u0434\u044b \u0432\u043e \u0434\u0432\u043e\u0440\u0435\n"
            "1\n"
            "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0432\u0441\u0435 \u043a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0438"
        )

        self.assertEqual(
            clean_ticker_comment_text(text, author_name="\u0421\u0435\u0440\u0451\u0433\u0430 \u0421\u0442\u0435\u043f\u0443\u0448\u0435\u0432"),
            "\u041d\u0435\u0442 \u0432\u043e\u0434\u044b \u0432\u043e \u0434\u0432\u043e\u0440\u0435",
        )

    def test_cleans_ticker_comment_when_author_name_is_only_text(self):
        text = "\u0421\u0435\u0440\u0451\u0433\u0430 \u0421\u0442\u0435\u043f\u0443\u0448\u0435\u0432\n\u0432\u0447\u0435\u0440\u0430 \u0432 23:35"

        self.assertEqual(clean_ticker_comment_text(text), "")

    def test_cleans_ticker_comment_leading_person_name_without_author_field(self):
        text = "\u0413\u0430\u043b\u0438\u043d\u0430 \u041d\u043e\u0432\u0438\u043a\u043e\u0432\u0430\n\u0411\u043b\u0430\u0433\u043e\u0434\u0430\u0440\u0438\u043c \u0432\u0430\u0441 \u0437\u0430 \u0440\u0435\u0430\u043a\u0446\u0438\u044e"

        self.assertEqual(
            clean_ticker_comment_text(text),
            "\u0411\u043b\u0430\u0433\u043e\u0434\u0430\u0440\u0438\u043c \u0432\u0430\u0441 \u0437\u0430 \u0440\u0435\u0430\u043a\u0446\u0438\u044e",
        )

    def test_cleans_ticker_comment_embedded_person_names(self):
        text = (
            "\u0412\u0438\u043a\u0442\u043e\u0440 \u0422\u0440\u0438\u0444\u043e\u043d\u043e\u0432\n"
            "\u0414\u043b\u044f \u0441\u0435\u0431\u044f \u0432\u044b\u0432\u043e\u0434\u044b \u0441\u0434\u0435\u043b\u0430\u043b\u0438\n"
            "\u0421\u0442\u0430\u043d\u0438\u0441\u043b\u0430\u0432 \u0420\u043e\u043c\u0430\u043d\u043e\u0432\n"
            "\u043d\u0443 \u0432\u043e\u0442, \u0441\u043d\u043e\u0432\u0430 \u0442\u0435\u043c\u0430 \u0434\u0432\u043e\u0440\u043e\u0432"
        )

        self.assertEqual(
            clean_ticker_comment_text(text),
            "\u0414\u043b\u044f \u0441\u0435\u0431\u044f \u0432\u044b\u0432\u043e\u0434\u044b \u0441\u0434\u0435\u043b\u0430\u043b\u0438\n"
            "\u043d\u0443 \u0432\u043e\u0442, \u0441\u043d\u043e\u0432\u0430 \u0442\u0435\u043c\u0430 \u0434\u0432\u043e\u0440\u043e\u0432",
        )

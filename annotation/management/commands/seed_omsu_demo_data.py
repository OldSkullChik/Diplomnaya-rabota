from django.core.management.base import BaseCommand
from django.utils import timezone

from annotation.models import OmsuArea, OmsuDashboardSnapshot, OmsuLatestComment


DEMO_AREAS = [
    {
        "slug": "nizhny-novgorod",
        "name": "Нижний Новгород",
        "area_type": "городской округ",
        "head_name": "Глава города: требует подтверждения",
        "area": 466.50,
        "population": 1221000,
        "score": -34,
        "previous": -41,
        "probability": 0.72,
        "polygon": [[430, 225], [560, 210], [615, 280], [585, 355], [470, 370], [405, 300]],
        "comment": "Жители снова жалуются на запах канализации и сроки реакции городских служб.",
        "topics": [["Канализация", 38], ["Дворы", 27], ["Мусор", 19], ["Отопление", 16]],
    },
    {
        "slug": "dzherzhinsk",
        "name": "Дзержинск",
        "area_type": "городской округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 421.00,
        "population": 218000,
        "score": -18,
        "previous": -22,
        "probability": 0.58,
        "polygon": [[275, 265], [405, 245], [430, 330], [365, 405], [255, 385], [230, 310]],
        "comment": "В части домов жители пишут о слабом напоре воды после ремонтных работ.",
        "topics": [["Вода", 44], ["Отопление", 25], ["Дворы", 18], ["Мусор", 13]],
    },
    {
        "slug": "bor",
        "name": "Бор",
        "area_type": "городской округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 3584.00,
        "population": 119000,
        "score": 12,
        "previous": 4,
        "probability": 0.21,
        "polygon": [[455, 95], [610, 115], [655, 205], [560, 210], [430, 225], [395, 145]],
        "comment": "Отмечают уборку снега на центральных улицах, но дворы остаются спорной темой.",
        "topics": [["Благоустройство", 36], ["Дворы", 31], ["Мусор", 22], ["Вода", 11]],
    },
    {
        "slug": "kstovo",
        "name": "Кстовский округ",
        "area_type": "муниципальный округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 1225.00,
        "population": 119500,
        "score": -63,
        "previous": -57,
        "probability": 0.91,
        "polygon": [[585, 355], [735, 325], [805, 425], [715, 515], [570, 480], [525, 405]],
        "comment": "Последний поток обращений связан с переполненными контейнерными площадками.",
        "topics": [["Мусор", 52], ["Дворы", 20], ["Власть", 16], ["Другое ЖКХ", 12]],
    },
    {
        "slug": "balakhna",
        "name": "Балахнинский округ",
        "area_type": "муниципальный округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 1020.00,
        "population": 73000,
        "score": -7,
        "previous": -13,
        "probability": 0.39,
        "polygon": [[250, 115], [395, 145], [430, 225], [275, 265], [190, 215]],
        "comment": "Появились вопросы по отключению воды, но часть сообщений носит информационный характер.",
        "topics": [["Вода", 34], ["Отопление", 24], ["Мусор", 23], ["Дворы", 19]],
    },
    {
        "slug": "arzamas",
        "name": "Арзамас",
        "area_type": "городской округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 613.00,
        "population": 103000,
        "score": 28,
        "previous": 19,
        "probability": 0.12,
        "polygon": [[320, 455], [470, 430], [570, 480], [535, 570], [380, 585], [295, 525]],
        "comment": "Жители обсуждают новые правила вывоза растительных отходов и работу служб.",
        "topics": [["Мусор", 46], ["Благоустройство", 28], ["Дворы", 16], ["Тарифы", 10]],
    },
    {
        "slug": "vyksa",
        "name": "Выкса",
        "area_type": "городской округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 1864.00,
        "population": 82000,
        "score": 45,
        "previous": 37,
        "probability": 0.09,
        "polygon": [[120, 415], [255, 385], [320, 455], [295, 525], [155, 545], [80, 480]],
        "comment": "Позитивные реакции связаны с благоустройством общественных пространств.",
        "topics": [["Благоустройство", 55], ["Дворы", 19], ["Мусор", 15], ["Вода", 11]],
    },
    {
        "slug": "semenov",
        "name": "Семёновский округ",
        "area_type": "городской округ",
        "head_name": "Глава округа: требует подтверждения",
        "area": 3900.00,
        "population": 45000,
        "score": -48,
        "previous": -36,
        "probability": 0.86,
        "polygon": [[610, 115], [765, 145], [840, 245], [735, 325], [615, 280], [655, 205]],
        "comment": "В последнем комментарии снова поднимается тема качества холодной воды.",
        "topics": [["Вода", 61], ["Власть", 17], ["Дворы", 12], ["Другое ЖКХ", 10]],
    },
]


class Command(BaseCommand):
    help = "Seed demo OMSU dashboard slice for API and PyQt prototype."

    def handle(self, *args, **options):
        now = timezone.now()
        for index, item in enumerate(DEMO_AREAS, start=1):
            area, _ = OmsuArea.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "area_type": item["area_type"],
                    "head_name": item["head_name"],
                    "leadership": [
                        {"role": "Глава", "name": item["head_name"].replace("Глава округа: ", "").replace("Глава города: ", "")},
                        {"role": "ЖКХ и благоустройство", "name": "требует подтверждения"},
                        {"role": "Обращения граждан", "name": "требует подтверждения"},
                    ],
                    "territory_area_km2": item["area"],
                    "population": item["population"],
                    "description": "Демонстрационный срез для desktop/API прототипа. Значения заменяются производственным агрегатором.",
                    "geometry": {"type": "Polygon", "coordinates": item["polygon"]},
                    "display_order": index,
                    "is_active": True,
                },
            )
            negative = max(0, round((100 - item["score"]) * 8))
            positive = max(0, round((item["score"] + 100) * 3))
            neutral = 900 + index * 41
            charts = {
                "score_trend": [item["previous"], round((item["previous"] + item["score"]) / 2), item["score"]],
                "topic_distribution": item["topics"],
                "sentiment_balance": [
                    ["Негатив", negative],
                    ["Нейтрально", neutral],
                    ["Позитив", positive],
                ],
                "appeal_types": [
                    ["Жалобы", max(12, negative // 9)],
                    ["Вопросы", 28 + index],
                    ["Просьбы", 18 + index * 2],
                    ["Благодарности", max(5, positive // 20)],
                ],
                "negative_probability": [["Вероятность негатива", round(item["probability"] * 100)]],
                "comment_volume": [120 + index * 17, 145 + index * 11, 160 + index * 9, 138 + index * 15],
                "responsible_parties": [
                    ["Администрация", 34 + index],
                    ["УК/ТСЖ", 20 + index],
                    ["РСО", 14 + index],
                    ["Оператор ТКО", 12 + index],
                ],
                "quality_mix": [["Обычные", 84], ["Сложные", 13], ["Дубли", 3]],
            }
            OmsuDashboardSnapshot.objects.update_or_create(
                area=area,
                defaults={
                    "omsu_score": item["score"],
                    "previous_omsu_score": item["previous"],
                    "omsu_negative_probability": item["probability"],
                    "comments_total": negative + positive + neutral,
                    "comments_last_day": 55 + index * 9,
                    "negative_total": negative,
                    "neutral_total": neutral,
                    "positive_total": positive,
                    "top_topics": item["topics"],
                    "charts": charts,
                    "generated_at": now,
                },
            )
            OmsuLatestComment.objects.update_or_create(
                area=area,
                text=item["comment"],
                defaults={
                    "sentiment": "negative" if item["score"] < -25 else "positive" if item["score"] > 25 else "neutral",
                    "omsu_score": item["score"],
                    "source_name": "Демо-срез",
                    "published_at": now,
                    "received_at": now,
                },
            )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(DEMO_AREAS)} OMSU demo areas."))

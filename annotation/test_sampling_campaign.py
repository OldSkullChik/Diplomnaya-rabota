from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from .choices import SAMPLING_POOL_CONTROL, SAMPLING_POOL_GENERAL, SAMPLING_POOL_JKH_CANDIDATE
from .models import AnnotationCampaign, SourceRecord
from .sampling import score_jkh_candidate
from .views import records_available_for_user


class JkhCandidateScoringTests(TestCase):
    def test_strong_housing_signal_is_selected(self):
        score, reasons = score_jkh_candidate(
            "Мы мерзнем, когда решат проблему?",
            "Управляющая компания не чинит отопление в подъезде.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertTrue(reasons)

    def test_unrelated_greeting_is_not_selected(self):
        score, reasons = score_jkh_candidate("Поздравляю команду с победой!", "Итоги турнира")

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_short_reaction_under_housing_post_is_selected_by_post_context(self):
        score, reasons = score_jkh_candidate(
            "Какие хмурые лица в зале!",
            "Управляющая компания не вывозит мусор и не чистит двор.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertIn("selection_basis: post context", reasons)

    def test_contextual_service_reaction_under_housing_post_is_selected(self):
        score, reasons = score_jkh_candidate(
            "Спасибо, что наконец вывезли!",
            "Контейнерная площадка во дворе была переполнена мусором.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertIn("selection_basis: post context", reasons)

    def test_hot_water_figure_of_speech_under_ice_rink_post_is_not_selected(self):
        score, reasons = score_jkh_candidate(
            "А чё его горячей водой привезенной из Байкала будут заливать?",
            "В парке зальют новый ледовый каток.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_road_safety_with_moose_is_not_selected(self):
        score, reasons = score_jkh_candidate(
            "Вдоль дорог нужны ограждения от лосей и вырубка кустов.",
            "На трассах выросло число ДТП из-за лосей.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_transport_request_does_not_inherit_yard_context(self):
        score, reasons = score_jkh_candidate(
            "Автобус не застаёт электрички, к кому обратиться для решения проблемы?",
            "Напомнили правила безопасности в дворовых территориях.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_sewerage_odour_complaint_is_selected_from_full_context(self):
        score, reasons = score_jkh_candidate(
            "Почему вы не работаете на результат, когда запахов в городе не будет вообще?",
            "Водоканал отвечает за станцию аэрации и обещает уменьшить запахи.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertIn("selection_basis: post context", reasons)

    def test_public_improvement_oversight_remains_selected(self):
        score, reasons = score_jkh_candidate(
            "Депутаты должны контролировать благоустройство сада и результат работ.",
            "Объявлен конкурс по благоустройству общественного пространства.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertTrue(reasons)

    def test_new_apartment_construction_is_not_common_property_maintenance(self):
        score, reasons = score_jkh_candidate(
            "Предоставлен земельный участок под строительство многоквартирного дома.",
            "Обсуждается новый строительный проект.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_church_construction_does_not_inherit_improvement_context(self):
        score, reasons = score_jkh_candidate(
            "Никакого большинства за строительство церкви под окнами нет.",
            "Благоустройство территории у строящегося храма завершат после строительных работ.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_spiritual_centre_dispute_on_yard_is_not_jkh(self):
        score, reasons = score_jkh_candidate(
            "Где теперь гулять детям?",
            "Вместо площадки на придомовой территории жителям предложили строительство Духпросцентра.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_waterfront_development_does_not_inherit_improvement_context(self):
        score, reasons = score_jkh_candidate(
            "Что-то мы приуныли.",
            "Благоустройство набережной уже наполовину готово, здесь появятся новые жилые дома и бизнес-центр.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_cultural_landmark_presentation_is_not_jkh_improvement(self):
        score, reasons = score_jkh_candidate(
            "Красиво!",
            "После благоустройства Шуховскую башню представили публике как туристский объект.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_atomic_station_post_does_not_turn_price_joke_into_heating_case(self):
        score, reasons = score_jkh_candidate(
            "Отопление бесплатно! Ню-ню.",
            "Выкса может стать площадкой для строительства АЭС.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_industrial_treatment_plant_construction_is_not_jkh(self):
        score, reasons = score_jkh_candidate(
            "Куда делись деньги на старые очистные?",
            "Пивзавод намерен построить очистные сооружения в рамках благоустройства производственной площадки.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_ice_palace_construction_is_not_yard_improvement(self):
        score, reasons = score_jkh_candidate(
            "Городу нужен этот объект.",
            "Ледовый дворец почти готов, на прилегающей дворовой территории укладывают асфальт.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_ice_arena_opening_is_not_public_improvement(self):
        score, reasons = score_jkh_candidate(
            "Когда откроется?",
            "Ледовая арена готовится к открытию, снаружи идут работы по благоустройству площади.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_stadium_master_plan_is_not_municipal_service(self):
        score, reasons = score_jkh_candidate(
            "Другой стадион давно заброшен.",
            "Завершается мастер-план по развитию стадиона, территорию благоустроят для спорта.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_snow_weather_warning_is_not_cleaning_service_post(self):
        score, reasons = score_jkh_candidate(
            "Администрация, очнитесь!",
            "Ожидается сильный снег; службы готовы к уборке улиц, действует предупреждение о неблагоприятной погоде.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_hospital_renovation_is_not_municipal_improvement(self):
        score, reasons = score_jkh_candidate(
            "Спасибо всем причастным!",
            "На ремонт ЦРБ направлены средства, включая благоустройство территории больницы.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_weapon_incident_in_stairwell_is_not_building_maintenance(self):
        score, reasons = score_jkh_candidate(
            "Сапер походу.",
            "Мужчина в алкогольном опьянении зашел в подъезд с оружием и сломал дверь, жители позвонили в 112.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_teen_vandalism_in_stairwell_is_not_building_maintenance(self):
        score, reasons = score_jkh_candidate(
            "Пишите заявление в полицию.",
            "Несовершеннолетние подростки портят подъезд и двери соседей, разговор с родителями не помог.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_stairwell_argument_without_maintenance_is_not_selected(self):
        score, reasons = score_jkh_candidate(
            "А других кто нецензурно в подъезде орет или оскорбляет на площадках?",
            "Жители обсуждают меры поведения.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_stairwell_cleaning_problem_remains_selected(self):
        score, reasons = score_jkh_candidate(
            "В подъезде грязь, уборки уже две недели нет.",
            "Жители дома направили обращение об отсутствии уборки в подъезде.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertTrue(reasons)

    def test_cold_radiators_remain_heating_signal(self):
        score, reasons = score_jkh_candidate(
            "В одной комнате включили, а в остальных холодные батареи.",
            "В доме отсутствует отопление, жители жалуются на холодные батареи.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertTrue(reasons)

    def test_short_location_reply_under_water_outage_post_is_selected_by_post(self):
        score, reasons = score_jkh_candidate(
            "Мэрия Нижнего Новгорода, Село Чистое Поле.",
            "Водоканал устраняет аварию и временно отключил воду.",
        )

        self.assertGreaterEqual(score, 7)
        self.assertIn("selection_basis: post context", reasons)

    def test_labour_policy_post_does_not_select_unrelated_reaction(self):
        score, reasons = score_jkh_candidate(
            "Неужели мозгов хватило?",
            "Для мигрантов по трудовым патентам разрешили работу в сфере водоснабжения.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_utility_problem_in_comment_does_not_redefine_generic_post(self):
        score, reasons = score_jkh_candidate(
            "У нас во дворе контейнеры переполнены, мусор не вывозят месяц.",
            "Глава округа рассказал о работе администрации.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])

    def test_heating_question_in_comment_does_not_redefine_generic_post(self):
        score, reasons = score_jkh_candidate(
            "Где отопление? Обещали, и тишина.",
            "Администрация ответила на вопросы жителей.",
        )

        self.assertLess(score, 7)
        self.assertEqual(reasons, [])


class JkhSamplingCampaignTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="labeler", password="StrongPass123")
        self.user.profile.is_approved = True
        self.user.profile.save(update_fields=["is_approved"])
        self.candidate = self.create_record(
            "Когда уже решат эту проблему?",
            "Управляющая компания оставила дом без горячей воды и отопления.",
        )
        self.general_a = self.create_record("Поздравляем артистов с выступлением.")
        self.general_b = self.create_record("Погода сегодня солнечная и теплая.")

    def create_record(self, text, post_text=""):
        return SourceRecord.objects.create(
            text=text,
            post_text=post_text,
            source_hash=SourceRecord.build_hash(text, post_text),
        )

    def apply_campaign(self):
        call_command(
            "prepare_jkh_sampling_campaign",
            "--apply",
            "--ratio",
            "100",
            "--threshold",
            "7",
            "--seed",
            "42",
            stdout=StringIO(),
        )

    def test_dry_run_writes_preview_without_changing_queue(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "preview.csv"
            stdout = StringIO()

            call_command(
                "prepare_jkh_sampling_campaign",
                "--preview-output",
                str(output),
                stdout=stdout,
            )

            self.assertTrue(output.exists())
            self.assertIn("likely_jkh_candidates=1", stdout.getvalue())
            self.assertIn("selection_subject=post_context_only", stdout.getvalue())
            self.assertFalse(AnnotationCampaign.objects.exists())
            self.assertEqual(
                set(SourceRecord.objects.values_list("sampling_pool", flat=True)),
                {SAMPLING_POOL_GENERAL},
            )

    def test_apply_activates_candidate_and_sparse_control_queue(self):
        self.apply_campaign()

        campaign = AnnotationCampaign.objects.get(key="jkh_enrichment")
        self.candidate.refresh_from_db()
        available_ids = set(records_available_for_user(self.user).values_list("id", flat=True))

        self.assertTrue(campaign.is_active)
        self.assertEqual(campaign.candidate_count, 1)
        self.assertEqual(campaign.control_count, 1)
        self.assertEqual(self.candidate.sampling_pool, SAMPLING_POOL_JKH_CANDIDATE)
        self.assertEqual(SourceRecord.objects.filter(sampling_pool=SAMPLING_POOL_CONTROL).count(), 1)
        self.assertEqual(len(available_ids), 2)
        self.assertIn(self.candidate.id, available_ids)

    def test_paused_general_record_cannot_be_opened_during_campaign(self):
        self.apply_campaign()
        paused = SourceRecord.objects.get(sampling_pool=SAMPLING_POOL_GENERAL)
        client = Client()
        client.login(username=self.user.username, password="StrongPass123")

        response = client.get(reverse("annotate_record", args=[paused.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("annotate_next"))

    def test_disable_restores_general_queue_without_deleting_marks(self):
        self.apply_campaign()

        call_command("prepare_jkh_sampling_campaign", "--disable", stdout=StringIO())

        campaign = AnnotationCampaign.objects.get(key="jkh_enrichment")
        available_ids = set(records_available_for_user(self.user).values_list("id", flat=True))
        self.assertFalse(campaign.is_active)
        self.assertEqual(available_ids, {self.candidate.id, self.general_a.id, self.general_b.id})

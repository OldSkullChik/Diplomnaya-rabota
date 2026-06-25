PROFILE_ROLE_STUDENT = "student"
PROFILE_ROLE_ADMIN = "admin"

PROFILE_ROLE_CHOICES = [
    (PROFILE_ROLE_STUDENT, "Студент"),
    (PROFILE_ROLE_ADMIN, "Администратор разметки"),
]

SAMPLING_POOL_GENERAL = "general"
SAMPLING_POOL_JKH_CANDIDATE = "jkh_candidate"
SAMPLING_POOL_CONTROL = "control"

SAMPLING_POOL_CHOICES = [
    (SAMPLING_POOL_GENERAL, "Общий пул"),
    (SAMPLING_POOL_JKH_CANDIDATE, "Кандидат ЖКХ"),
    (SAMPLING_POOL_CONTROL, "Контрольная выборка"),
]

RELEVANCE_CHOICES = [
    ("yes", "Да, относится к ЖКХ"),
    ("no", "Нет, не относится к ЖКХ"),
    ("unsure", "Не уверен(а)"),
]

JKH_TOPIC_CHOICES = [
    ("not_jkh", "Не ЖКХ"),
    ("heating_hot_water", "Отопление и горячая вода"),
    ("cold_water_sewerage", "Холодная вода и канализация"),
    ("waste_cleaning", "Мусор и уборка"),
    ("house_common_property", "Подъезд, лифт, крыша, подвал"),
    ("yard_area", "Двор и придомовая территория"),
    ("payments_tariffs", "Тарифы, квитанции, счетчики"),
    ("management_company", "Работа УК/ТСЖ"),
    ("public_authorities", "Работа администрации/госорганов"),
    ("other_jkh", "Другое ЖКХ"),
]

AUTHORITY_ASPECT_CHOICES = [
    ("not_applicable", "Не применимо"),
    ("no_action", "Бездействие"),
    ("slow_response", "Затягивание сроков"),
    ("poor_quality", "Некачественная работа"),
    ("communication", "Информирование и ответы гражданам"),
    ("tariff_policy", "Тарифы и начисления"),
    ("supervision", "Контроль и надзор"),
    ("positive_feedback", "Положительная оценка работы"),
    ("other", "Другое"),
]

SENTIMENT_CHOICES = [
    ("negative", "Негативная"),
    ("neutral", "Нейтральная"),
    ("positive", "Позитивная"),
    ("mixed", "Смешанная/неоднозначная"),
]

APPEAL_TYPE_CHOICES = [
    ("complaint", "Жалоба"),
    ("question", "Вопрос"),
    ("request", "Просьба"),
    ("demand", "Требование"),
    ("suggestion", "Предложение"),
    ("gratitude", "Благодарность"),
    ("opinion", "Мнение"),
    ("info", "Информирование"),
    ("other", "Другое"),
]

RESPONSIBLE_PARTY_CHOICES = [
    ("management_company", "УК/ТСЖ"),
    ("resource_provider", "Ресурсоснабжающая организация"),
    ("local_administration", "Администрация"),
    ("housing_inspection", "Госжилинспекция/надзор"),
    ("waste_operator", "Регоператор по мусору"),
    ("residents", "Жители/соседи"),
    ("specific_person", "Конкретное лицо"),
    ("unknown", "Неясно"),
    ("not_applicable", "Не применимо"),
]

SARCASM_CHOICES = [
    ("no", "Нет"),
    ("yes", "Да"),
    ("unsure", "Не уверен(а)"),
]

QUALITY_CHOICES = [
    ("normal", "Обычная запись"),
    ("difficult", "Сложная/спорная"),
    ("spam", "Мусор/спам"),
    ("duplicate", "Дубликат"),
    ("no_context", "Не хватает контекста"),
]

ANNOTATION_STATUS_SUBMITTED = "submitted"
ANNOTATION_STATUS_APPROVED = "approved"
ANNOTATION_STATUS_REJECTED = "rejected"

ANNOTATION_STATUS_CHOICES = [
    (ANNOTATION_STATUS_SUBMITTED, "Ожидает проверки"),
    (ANNOTATION_STATUS_APPROVED, "Принята"),
    (ANNOTATION_STATUS_REJECTED, "Отклонена"),
]

SCORE_KIND_AWARD = "award"
SCORE_KIND_PENALTY = "penalty"

SCORE_KIND_CHOICES = [
    (SCORE_KIND_AWARD, "Начисление"),
    (SCORE_KIND_PENALTY, "Штраф"),
]

import re

from .choices import SAMPLING_POOL_CONTROL, SAMPLING_POOL_JKH_CANDIDATE
from .models import AnnotationCampaign


JKH_CAMPAIGN_KEY = "jkh_enrichment"
CAMPAIGN_POOLS = [SAMPLING_POOL_JKH_CANDIDATE, SAMPLING_POOL_CONTROL]

# These signals intentionally favor precision over recall: candidate selection
# accelerates human review, but never replaces the submitted label.
JKH_SIGNALS = (
    (
        "direct_jkh",
        "ЖКХ, коммунальная услуга или управляющая организация",
        12,
        r"\bжкх\b|коммунальн\w*\s+(?:услуг|служб|авари|платеж|проблем)"
        r"|управляющ\w*\s+компан|\bтсж\b|\bжилинспекц",
    ),
    (
        "water_heat",
        "вода, канализация или отопление",
        10,
        r"водоканал|водоснаб|водоотвед|канализац|станци\w*\s+аэрац|теплоснаб|теплосет|отоплен"
        r"|отключ\w*\s+(?:вод|тепл)"
        r"|батаре\w*.{0,40}(?:холод|не\s+гре|не\s+работ|чуть\s+теп)"
        r"|(?:холод|не\s+гре).{0,40}батаре"
        r"|(?:нет|без|дали|подал|вернут|когда|давлен|ржав|теч)\w*.{0,40}(?:горяч|холодн)\w*\s+вод"
        r"|(?:горяч|холодн)\w*\s+вод.{0,40}(?:нет|без|отключ|дали|подал|вернут|когда|давлен|ржав|теч)",
    ),
    (
        "waste",
        "вывоз мусора или контейнерная площадка",
        9,
        r"\bтко\b|регоператор|вывоз\w*\s+мусор|мусор\w*\s+(?:контейнер|площад)"
        r"|контейнерн\w*\s+площад",
    ),
    (
        "building",
        "содержание многоквартирного дома",
        9,
        r"общедом|содержан\w*\s+многоквартир|капремонт|домофон"
        r"|(?:гряз|убор|ремонт|затоп|освещ|двер|окн|трещ|вон|запах|разруша|не\s+убир|не\s+мы)\w*.{0,40}подъезд"
        r"|подъезд\w*.{0,40}(?:гряз|убор|ремонт|затоп|освещ|двер|окн|трещ|вон|запах|разруша|не\s+убир|не\s+мы)"
        r"|(?:лифт|подвал|крыш\w*)\s+(?:дом|подъезд|теч|ремонт|не\s+работ)",
    ),
    (
        "billing",
        "начисления или приборы учета ЖКХ",
        8,
        r"квитанц|счетчик|прибор\w*\s+учет"
        r"|тариф\w*\s+(?:на\s+)?(?:вод|тепл|коммун|вывоз)",
    ),
    (
        "yard",
        "двор или придомовая территория",
        7,
        r"придомов|дворов\w*\s+террит"
        r"|двор\w*.*(?:мусор|уборк|снег|освещ|фонар|площадк|луж|асфальт)",
    ),
    (
        "improvement",
        "городское благоустройство",
        7,
        r"благоустрой|ливнев|уличн\w*\s+освещ"
        r"|(?:уборк|вывоз|очист)\w*.*(?:улиц|снег|двор)",
    ),
    (
        "authority",
        "обращение к органам власти",
        2,
        r"администрац|госжилинспекц|обращен\w*\s+в|жалоб\w*\s+в",
    ),
)
COMPILED_SIGNALS = tuple(
    (key, label, points, re.compile(pattern, flags=re.IGNORECASE))
    for key, label, points, pattern in JKH_SIGNALS
)
POST_OUT_OF_SCOPE = re.compile(
    r"автобус|маршрутн\w*\s+сет|электричк|общественн\w*\s+транспорт"
    r"|автоинспект|дорожн\w*\s+происшеств|\bдтп\b|лос\w*|правил\w*\s+безопасност"
    r"|мигрант|иностранн\w*\s+граждан|трудов\w*\s+патент"
    r"|земельн\w*\s+участ|под\s+строительств|новострой|застройщ|жил\w*\s+комплекс"
    r"|(?:появ|планир|постро|создад|стро)\w*.{0,80}(?:нов\w*\s+)?жил\w*\s+дом"
    r"|(?:нов\w*\s+)?жил\w*\s+дом.{0,80}(?:появ|планир|постро|создад|стро)\w*|бизнес-центр"
    r"|церк\w*|храм\w*|духовн\w*\s+центр|дух\W*прос\W*центр|\bдпц\b"
    r"|\bаэс\b|атомн\w*\s+(?:электростанц|станц)|экопромышленн\w*\s+парк"
    r"|шуховск\w*\s+баш|культурн\w*\s+наслед|туристск\w*\s+объект"
    r"|пивзавод|очистн\w*\s+сооруж.{0,100}(?:завод|производственн\w*\s+площад)"
    r"|(?:завод|производственн\w*\s+площад).{0,100}очистн\w*\s+сооруж"
    r"|ледов\w*\s+(?:дворец|арен)|стадион\w*|спортивн\w*\s+(?:арен|объект|комплекс)"
    r"|ожида\w*.{0,30}сильн\w*\s+снег|метеопредупрежд|неблагоприятн\w*\s+погод"
    r"|(?:проверил\w*\s+качество\s+ремонт|ремонт\w*\s+больниц|ремонт\w*\s+в\s+.{0,30}\bцрб\b|"
    r"благоустр\w*\s+территор\w*\s+(?:црб|больниц|поликлиник))"
    r"|(?:оруж|полици|позвонил\w*\s+в\s+112|подростк|хулиган|алкогольн\w*\s+опьян).{0,140}(?:подъезд|двер)"
    r"|(?:подъезд|двер).{0,140}(?:оруж|полици|112|подростк|хулиган|алкогольн\w*\s+опьян)",
    flags=re.IGNORECASE,
)


def score_signals(content, prefix):
    content = content.lower().replace("ё", "е")
    score = 0
    reasons = []
    for key, label, points, pattern in COMPILED_SIGNALS:
        if pattern.search(content):
            score += points
            reasons.append(f"{prefix}/{key}: {label} (+{points})")
    return score, reasons


def score_jkh_candidate(_comment_text, post_text=""):
    post_score, post_reasons = score_signals(post_text, "post")
    normalized_post = post_text.lower().replace("ё", "е")

    # The post defines the subject of the source record. The comment is the
    # public reaction to label later, and must not redefine the subject.
    if post_score >= 7 and not POST_OUT_OF_SCOPE.search(normalized_post):
        return post_score, ["selection_basis: post context"] + post_reasons

    return 0, []


def active_sampling_campaign():
    return AnnotationCampaign.objects.filter(key=JKH_CAMPAIGN_KEY, is_active=True).first()


def filter_for_campaign(queryset, campaign=None):
    campaign = campaign if campaign is not None else active_sampling_campaign()
    if campaign:
        return queryset.filter(sampling_pool__in=CAMPAIGN_POOLS)
    return queryset

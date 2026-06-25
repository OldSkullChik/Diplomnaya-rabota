from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .choices import (
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_REJECTED,
)
from .models import Annotation
from .permissions import user_is_annotation_admin


class SignUpForm(UserCreationForm):
    public_name = forms.CharField(label="Как вас показывать в статистике", max_length=120, required=False)
    first_name = forms.CharField(label="Имя", max_length=120, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=120, required=False)
    email = forms.EmailField(label="Email", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Логин"
        self.fields["username"].help_text = "Можно использовать ник или фамилию латиницей."
        self.fields["password1"].label = "Пароль"
        self.fields["password2"].label = "Повтор пароля"
        self.fields["password1"].help_text = "Минимум 8 символов; лучше не использовать простой цифровой пароль."
        self.fields["password2"].help_text = ""

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "public_name", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
            user.profile.public_name = self.cleaned_data.get("public_name", "")
            user.profile.save(update_fields=["public_name"])
        return user


class AnnotationForm(forms.ModelForm):
    required_choice_fields = (
        "jkh_relevance",
        "jkh_topic",
        "authority_aspect",
        "sentiment",
        "appeal_type",
        "responsible_party",
        "sarcasm",
        "quality",
    )
    not_jkh_forced_values = {
        "jkh_topic": "not_jkh",
        "authority_aspect": "not_applicable",
        "responsible_party": "not_applicable",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.required_choice_fields:
            choices = list(self.fields[field_name].choices)
            if choices and choices[0][0] != "":
                self.fields[field_name].choices = [("", "Выберите вариант")] + choices
            if not self.is_bound:
                self.fields[field_name].initial = ""
        for field_name in self.not_jkh_forced_values:
            self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()
        relevance = cleaned_data.get("jkh_relevance")
        if relevance == "no":
            cleaned_data.update(self.not_jkh_forced_values)
            return cleaned_data
        for field_name in self.not_jkh_forced_values:
            if not cleaned_data.get(field_name):
                self.add_error(field_name, "Выберите вариант.")
        return cleaned_data

    class Meta:
        model = Annotation
        fields = (
            "jkh_relevance",
            "jkh_topic",
            "authority_aspect",
            "sentiment",
            "appeal_type",
            "responsible_party",
            "sarcasm",
            "quality",
            "student_comment",
        )
        widgets = {
            "student_comment": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Коротко поясните спорный выбор, если нужно."}
            ),
        }
        labels = {
            "jkh_relevance": "Относится к ЖКХ?",
            "jkh_topic": "Тема ЖКХ",
            "authority_aspect": "Работа органов/служб",
            "sentiment": "Тональность",
            "appeal_type": "Тип обращения",
            "responsible_party": "Ответственная сторона",
            "sarcasm": "Сарказм или ирония",
            "quality": "Качество записи",
            "student_comment": "Комментарий к разметке",
        }
        help_texts = {
            "jkh_relevance": (
                "Определяется по теме поста. Да — пост посвящен ЖКХ, городской среде или "
                "благоустройству, даже если комментарий является короткой реакцией. Комментарий "
                "не меняет направление записи. Нет — пост не про ЖКХ. Не уверен(а) — только "
                "когда предмет поста нельзя надежно понять."
            ),
            "jkh_topic": (
                "Выберите главную ЖКХ-тему ситуации из поста. Комментарий помогает описать "
                "реакцию, но не переопределяет тему. "
                "Примеры: снег во дворе — двор и придомовая территория; "
                "квитанции — тарифы; сломанный лифт — подъезд/лифт. Если выбрано Нет по ЖКХ, поле "
                "автоматически станет Не ЖКХ."
            ),
            "authority_aspect": (
                "Отмечайте оценку работы органов, УК или служб в комментарии с учетом ситуации поста. Примеры: не чистят "
                "снег — некачественная работа; не отвечают людям — информирование и ответы; ничего "
                "не делают — бездействие. Для не-ЖКХ ставится Не применимо."
            ),
            "sentiment": (
                "Тон комментария. Негативная — жалоба, недовольство, критика. Позитивная — похвала "
                "или поддержка. Нейтральная — факт без оценки. Смешанная — есть разные оценки сразу."
            ),
            "appeal_type": (
                "Форма высказывания. Жалоба — человеку плохо из-за проблемы; вопрос — просит "
                "объяснить; просьба/требование — хочет действия; мнение — просто оценка ситуации."
            ),
            "responsible_party": (
                "Кого пользователь считает ответственным. Примеры: двор/подъезд — УК/ТСЖ; вода или "
                "тепло — ресурсоснабжающая организация; дороги/городские службы — администрация. "
                "Для не-ЖКХ ставится Не применимо."
            ),
            "sarcasm": (
                "Да, если смысл сказан через иронию: «ну конечно, опять идеально убрали снег». "
                "Не уверен(а), если интонация спорная."
            ),
            "quality": (
                "Обычная запись — можно разметить. Сложная/спорная — смысл неоднозначен. "
                "Мусор/спам — бессодержательный текст, не связанный с понятным обсуждением. "
                "Короткая реакция под понятным постом сама по себе не является мусором. "
                "Не хватает контекста — без поста нельзя понять."
            ),
            "student_comment": (
                "Необязательное пояснение для проверяющего: почему выбран спорный вариант или чего "
                "не хватает в контексте."
            ),
        }


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(
        label="Решение",
        choices=[
            (ANNOTATION_STATUS_APPROVED, "Принять"),
            (ANNOTATION_STATUS_REJECTED, "Отклонить"),
        ],
    )
    award_points = forms.IntegerField(label="Начислить баллов", min_value=0, initial=1)
    penalty_points = forms.IntegerField(label="Штраф", min_value=0, initial=0)
    review_comment = forms.CharField(
        label="Комментарий администратора",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Что исправить или почему ответ принят."}),
    )

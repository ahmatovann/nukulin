"""Формы курсов: комментарии к урокам и отзывы о курсе."""
from django import forms

from .models import Comment, Review


class CommentForm(forms.ModelForm):
    """Комментарий к уроку (ФТ-30)."""

    class Meta:
        model = Comment
        fields = ('text',)
        labels = {'text': 'Ваш комментарий'}
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Спросите о непонятном или поделитесь тем, что помогло разобраться.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].widget.attrs['class'] = 'gc-input'

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        if len(text) < 3:
            raise forms.ValidationError('Комментарий слишком короткий — напишите хотя бы несколько слов.')
        return text


class ReviewForm(forms.ModelForm):
    """Отзыв о курсе с оценкой (ФТ-31)."""

    class Meta:
        model = Review
        fields = ('rating', 'text')
        labels = {'rating': 'Оценка курса', 'text': 'Отзыв'}
        widgets = {
            'rating': forms.RadioSelect,
            'text': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Что понравилось, чего не хватило, кому посоветуете этот курс.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].widget.attrs['class'] = 'gc-input'
        self.fields['rating'].choices = Review.RATING_CHOICES
        self.fields['rating'].empty_label = None


class AccessCodeForm(forms.Form):
    """Ввод кода доступа к закрытому курсу."""

    code = forms.CharField(
        label='Код доступа',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'gc-input gc-code-input',
            'placeholder': 'XXXX-XXXX',
            'autocomplete': 'off',
            'autocapitalize': 'characters',
            'spellcheck': 'false',
        }),
    )

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


def _luhn_ok(number):
    """Проверка контрольной цифры: ловит опечатки в номере карты."""
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit = digit * 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


class PaymentForm(forms.Form):
    """Форма учебной оплаты. Данные карты не сохраняются — в журнал идут только последние 4 цифры."""

    card_number = forms.CharField(
        label='Номер карты',
        max_length=23,
        widget=forms.TextInput(attrs={
            'class': 'gc-input', 'placeholder': '4242 4242 4242 4242',
            'inputmode': 'numeric', 'autocomplete': 'off',
        }),
    )
    expiry = forms.CharField(
        label='Срок действия',
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'gc-input', 'placeholder': 'ММ/ГГ',
            'inputmode': 'numeric', 'autocomplete': 'off',
        }),
    )
    cvv = forms.CharField(
        label='CVV',
        max_length=3,
        widget=forms.PasswordInput(attrs={
            'class': 'gc-input', 'placeholder': '123',
            'inputmode': 'numeric', 'autocomplete': 'off',
        }, render_value=False),
    )

    def clean_card_number(self):
        number = ''.join(ch for ch in self.cleaned_data['card_number'] if ch.isdigit())
        if len(number) != 16:
            raise forms.ValidationError('Номер карты — 16 цифр.')
        if not _luhn_ok(number):
            raise forms.ValidationError('Номер карты введён с ошибкой. Проверьте цифры.')
        return number

    def clean_expiry(self):
        import datetime
        value = self.cleaned_data['expiry'].strip()
        try:
            month_text, year_text = value.split('/')
            month, year = int(month_text), 2000 + int(year_text)
            if not 1 <= month <= 12:
                raise ValueError
        except ValueError:
            raise forms.ValidationError('Укажите срок в виде ММ/ГГ, например 08/29.')
        today = datetime.date.today()
        if (year, month) < (today.year, today.month):
            raise forms.ValidationError('Срок действия карты истёк.')
        return value

    def clean_cvv(self):
        cvv = self.cleaned_data['cvv'].strip()
        if not (cvv.isdigit() and len(cvv) == 3):
            raise forms.ValidationError('CVV — три цифры на обратной стороне карты.')
        return cvv

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

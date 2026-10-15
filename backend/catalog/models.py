from django.db import models
from django.conf import settings


class ManualOdds(models.Model):
    source = models.CharField('출처', max_length=20)
    event_id = models.CharField('경기 번호', max_length=200)
    prices = models.JSONField('수동 배당', default=dict)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='수정 관리자')
    updated_at = models.DateTimeField('수정 시각', auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'event_id'], name='manual_odds_event')]
        verbose_name = '수동 배당 설정'
        verbose_name_plural = '수동 배당 설정'


class Game(models.Model):
    class Category(models.TextChoices):
        BALL = "ball", "볼 게임"
        LADDER = "ladder", "사다리"
        CARDS = "cards", "카드 게임"
        SPORTS = "sports", "스포츠"
    name = models.CharField("게임명", max_length=100)
    slug = models.SlugField("주소 이름", max_length=100, unique=True, help_text="영문 소문자, 숫자, 하이픈과 밑줄로 입력하세요. 기존 링크 유지를 위해 등록 후 변경할 수 없습니다.")
    english_name = models.CharField("영문명", max_length=100, blank=True)
    category = models.CharField("분류", max_length=16, choices=Category.choices)
    symbol = models.CharField("표시 아이콘", max_length=8, default="🎮")
    description = models.TextField("게임 안내", blank=True, max_length=10000)
    is_published = models.BooleanField("게시", default=False)
    sort_order = models.PositiveIntegerField("표시 순서", default=0, help_text="숫자가 작은 게임부터 표시됩니다.")
    class Meta:
        verbose_name = "게임"
        verbose_name_plural = "게임"
        ordering = ["sort_order", "pk"]
    def __str__(self):
        return self.name

from django.db import models


class FeedSnapshot(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    payload = models.JSONField("경기·배당 데이터", default=dict)
    fetched_at = models.DateTimeField("조회 완료 시각", null=True, blank=True)
    syncing = models.BooleanField("조회 진행 중", default=False)
    started_at = models.DateTimeField("조회 시작 시각", null=True, blank=True)
    last_error = models.CharField("마지막 조회 안내", max_length=500, blank=True)

    class Meta:
        verbose_name = "경기·배당 전체 조회"
        verbose_name_plural = "경기·배당 전체 조회"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="sports_single_snapshot")]

    def __str__(self):
        return "The Odds API 경기·배당 저장본"

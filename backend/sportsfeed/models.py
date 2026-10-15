from django.db import models


class FeedSnapshot(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    payload = models.JSONField("경기·배당 데이터", default=dict)
    fetched_at = models.DateTimeField("조회 완료 시각", null=True, blank=True)
    syncing = models.BooleanField("조회 진행 중", default=False)
    started_at = models.DateTimeField("조회 시작 시각", null=True, blank=True)
    last_error = models.CharField("마지막 조회 안내", max_length=500, blank=True)

    class Meta:
        verbose_name = "API 수집·갱신"
        verbose_name_plural = "API 수집·갱신"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="sports_single_snapshot")]

    def __str__(self):
        return "The Odds API 경기·배당 저장본"


from django.conf import settings

class DemoSlip(models.Model):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='회원')
    source = models.CharField('게임 분류', max_length=12, default='sports', choices=[('sports', '스포츠'), ('powerball', '엔트리 파워볼')])
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    mode = models.CharField('배팅 방식', max_length=6, choices=[('single', '싱글'), ('multi', '멀티')])
    stake = models.PositiveBigIntegerField('선택당 배팅금액')
    total_stake = models.PositiveBigIntegerField('배팅금액')
    expected_return = models.PositiveBigIntegerField('적중예상금액')
    status = models.CharField('정산 상태', max_length=10, default='pending', choices=[('pending', '정산 대기'), ('won', '적중'), ('lost', '미적중'), ('void', '취소'), ('mixed', '혼합 결과')])
    credited_amount = models.PositiveBigIntegerField('적중금액', default=0)
    settled_at = models.DateTimeField('정산 완료 시각', null=True, blank=True)
    settled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='settled_demo_slips', verbose_name='최종 처리 관리자')
    legs = models.JSONField(default=list)
    created_at = models.DateTimeField('배팅 시각', auto_now_add=True)

    class Meta:
        verbose_name = '배팅 내역'
        verbose_name_plural = '배팅 내역'
        ordering = ['-pk']
        constraints = [
            models.UniqueConstraint(fields=['member', 'request_id'], name='demo_slip_member_request'),
            models.CheckConstraint(condition=models.Q(stake__gt=0, total_stake__gt=0), name='demo_slip_positive_stake'),
        ]


class DemoLeg(models.Model):
    slip = models.ForeignKey(DemoSlip, on_delete=models.PROTECT, related_name='results', verbose_name='테스트 접수')
    position = models.PositiveSmallIntegerField('선택 순번')
    selection = models.JSONField('접수 시 선택 정보', default=dict)
    result = models.CharField('경기 결과', max_length=8, default='pending', choices=[('pending', '대기'), ('won', '적중'), ('lost', '미적중'), ('void', '취소')])
    settled_at = models.DateTimeField('처리 시각', null=True, blank=True)
    settled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='settled_demo_legs', verbose_name='처리 관리자')

    class Meta:
        verbose_name = '경기 결과'
        verbose_name_plural = '경기 결과'
        ordering = ['slip_id', 'position']
        constraints = [models.UniqueConstraint(fields=['slip', 'position'], name='demo_leg_position')]

    def __str__(self):
        return f"#{self.slip_id} · {self.selection.get('home', '')} vs {self.selection.get('away', '')}"


class PowerballResult(models.Model):
    day = models.DateField('추첨 날짜')
    round_number = models.PositiveSmallIntegerField('일일 회차')
    global_round = models.PositiveBigIntegerField('엔트리 전체 회차', unique=True)
    balls = models.JSONField('일반볼')
    powerball = models.PositiveSmallIntegerField('파워볼')
    received_at = models.DateTimeField('수신 시각', auto_now_add=True)
    class Meta:
        verbose_name = '파워볼 공식 결과'
        verbose_name_plural = '파워볼 공식 결과'
        ordering = ['-day', '-round_number']
        constraints = [models.UniqueConstraint(fields=['day','round_number'], name='powerball_result_round'), models.CheckConstraint(condition=models.Q(round_number__gte=1, round_number__lte=288, powerball__lte=9), name='powerball_result_bounds')]
    def __str__(self): return f'{self.day} · {self.round_number}회차'


class PowerballSync(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField('공식 결과 조회·자동 정산', default=True)
    fetched_at = models.DateTimeField('마지막 정상 수신', null=True, blank=True)
    last_error = models.CharField('마지막 오류', max_length=500, blank=True)
    syncing = models.BooleanField(default=False, editable=False)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    class Meta:
        verbose_name = '파워볼 자동 정산 설정'
        verbose_name_plural = '파워볼 자동 정산 설정'
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='powerball_single_sync')]
    def __str__(self): return '엔트리 파워볼 결과 연동'


class OddsPortalSnapshot(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    payload = models.JSONField("수집 경기·배당·결과", default=dict)
    fetched_at = models.DateTimeField("최근 수집", null=True, blank=True)
    last_error = models.CharField("수집 오류", max_length=500, blank=True)

    class Meta:
        verbose_name = "OddsParsing"
        verbose_name_plural = "OddsParsing"

    def __str__(self):
        return "OddsParsing 경기·결과 저장본"


class OddsPortalCollectionJob(models.Model):
    options = models.JSONField('수집 선택',default=dict,blank=True)
    class Status(models.TextChoices):
        QUEUED = 'queued', '시작 대기'
        RUNNING = 'running', '수집 중'
        COMPLETE = 'complete', '전체 수집 완료'
        PARTIAL = 'partial', '일부 수집 / 실패 확인 필요'
        FAILED = 'failed', '수집 실패'
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='요청 관리자')
    day = models.DateField('수집 기준일 (한국 시간)')
    status = models.CharField('진행 상태', max_length=12, choices=Status.choices, default=Status.QUEUED)
    active_key = models.CharField(max_length=20, unique=True, null=True, editable=False, default='today')
    current_sport = models.CharField('현재 종목', max_length=100, blank=True)
    pages_total = models.PositiveIntegerField('대상 종목 수', default=0)
    pages_done = models.PositiveIntegerField('처리한 종목 수', default=0)
    match_count = models.PositiveIntegerField('수집 경기 수', default=0)
    reports = models.JSONField('종목별 결과', default=list)
    error = models.CharField('오류 안내', max_length=500, blank=True)
    created_at = models.DateTimeField('요청 시각', auto_now_add=True)
    updated_at = models.DateTimeField('최근 진행 시각', auto_now=True)
    finished_at = models.DateTimeField('종료 시각', null=True, blank=True)

    class Meta:
        verbose_name = 'OddsParsing 수집 이력'
        verbose_name_plural = 'OddsParsing 수집 이력'
        ordering = ['-pk']


class HarvesterSnapshot(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    payload = models.JSONField('Harvester 수집본', default=dict)
    fetched_at = models.DateTimeField('최근 수집', null=True, blank=True)

    class Meta:
        verbose_name = 'OddsHarvester'
        verbose_name_plural = 'OddsHarvester'

    def __str__(self): return 'OddsHarvester'


class HarvesterJob(models.Model):
    target_bookmaker=models.CharField('수집 업체',max_length=100,blank=True,default='')
    starts_from = models.DateTimeField('예정 경기 기준일시',null=True,blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='요청 관리자')
    mode = models.CharField('수집 종류', max_length=12, choices=[('upcoming','예정 경기'),('historic','과거 경기·결과'),('live','인플레이'),('all','전체')])
    sport = models.CharField('종목', max_length=30)
    day = models.DateField('한국 기준일')
    league = models.CharField('리그', max_length=150, blank=True)
    markets = models.CharField('수집 시장', max_length=200)
    limit = models.PositiveSmallIntegerField('최대 상세 수집 경기 수', default=10)
    status = models.CharField('상태', max_length=12, default='queued', choices=[('queued','시작 대기'),('running','수집 중'),('complete','완료'),('partial','일부 수집'),('failed','실패'),('cancelled','중지')])
    active_key = models.CharField(max_length=20, unique=True, null=True, default='harvester', editable=False)
    progress = models.CharField('진행 상황', max_length=250, blank=True)
    match_count = models.PositiveIntegerField('저장 경기 수', default=0)
    error = models.CharField('안내', max_length=1000, blank=True)
    created_at = models.DateTimeField('요청 시각', auto_now_add=True)
    updated_at = models.DateTimeField('최근 응답', auto_now=True)
    finished_at = models.DateTimeField('종료 시각', null=True, blank=True)

    class Meta:
        verbose_name = 'Harvester 수집 이력'
        verbose_name_plural = 'Harvester 수집 이력'
        ordering = ['-pk']


class InplaySnapshot(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    payload=models.JSONField('Inplay 수집본',default=dict)
    fetched_at=models.DateTimeField('최근 수집',null=True,blank=True)
    class Meta:
        verbose_name='Inplay'
        verbose_name_plural='Inplay'

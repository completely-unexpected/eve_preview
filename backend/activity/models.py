from django.db import models


class PagePresence(models.Model):
    last_ip=models.GenericIPAddressField('최근 접속 IP',null=True,blank=True)
    actor=models.CharField('계정',max_length=180)
    actor_kind=models.CharField('계정 구분',max_length=20,choices=[('member','회원'),('admin','관리자'),('partner','하위 협력사')])
    route=models.CharField('현재 화면 주소',max_length=500)
    last_seen=models.DateTimeField('마지막 확인',db_index=True)

    class Meta:
        verbose_name='사용자 현재 위치'
        verbose_name_plural='사용자 현재 위치'
        ordering=['-last_seen']
        constraints=[models.UniqueConstraint(fields=['actor','actor_kind'],name='presence_account')]


class ActivityLog(models.Model):
    created_at = models.DateTimeField('시각', auto_now_add=True, db_index=True)
    request_id = models.UUIDField('요청 번호', null=True, db_index=True)
    actor = models.CharField('계정', max_length=180, db_index=True)
    actor_kind = models.CharField('계정 구분', max_length=20, choices=[('member','회원'),('partner','하위 협력사'),('admin','관리자'),('anonymous','비로그인'),('system','자동 작업')], db_index=True)
    action = models.CharField('종류', max_length=20, choices=[('request','접속·요청'),('create','생성'),('update','수정'),('delete','삭제'),('relation','권한·연결 변경'),('bulk','일괄 생성')], db_index=True)
    path = models.CharField('경로', max_length=500, blank=True)
    method = models.CharField('요청 방식', max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField('응답 코드', null=True, blank=True)
    target_model = models.CharField('대상 종류', max_length=100, blank=True, db_index=True)
    target_id = models.CharField('대상 번호', max_length=100, blank=True, db_index=True)
    changes = models.JSONField('변경 전후·처리 정보', default=dict)

    class Meta:
        verbose_name = '통합 활동 로그'
        verbose_name_plural = '통합 활동 로그'
        ordering = ['-pk']

    def __str__(self):
        return f'{self.actor} · {self.get_action_display()} · {self.target_model or self.path}'

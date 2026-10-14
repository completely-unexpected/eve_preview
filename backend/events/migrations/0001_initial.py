from django.db import migrations, models

def seed(apps, schema_editor):
    Event=apps.get_model("events","Event")
    for values in [{'tag': 'WELCOME EVENT', 'title': '새로운 시작, 특별한 혜택', 'summary': '매일 새로운 이벤트를 만나보세요.', 'symbol': '🎁', 'body': '이벤트 화면 확인을 위한 샘플 안내입니다. 실제 참여 신청이나 혜택 지급은 제공하지 않습니다.', 'is_published': True, 'sort_order': 0}, {'tag': 'DAILY EVENT', 'title': '오늘의 플레이, 오늘의 즐거움', 'summary': '일상에 즐거운 순간을 더하세요.', 'symbol': '🏆', 'body': '이벤트 화면 확인을 위한 샘플 안내입니다. 실제 참여 신청이나 혜택 지급은 제공하지 않습니다.', 'is_published': True, 'sort_order': 1}, {'tag': 'QUIZ EVENT', 'title': '함께 즐기는 퀴즈 이벤트', 'summary': '새로운 퀴즈와 재미있는 이야기를 만나보세요.', 'symbol': '💡', 'body': '이벤트 화면 확인을 위한 샘플 안내입니다. 실제 참여 신청이나 혜택 지급은 제공하지 않습니다.', 'is_published': True, 'sort_order': 2}, {'tag': 'COMMUNITY EVENT', 'title': '함께 만드는 특별한 순간', 'summary': '다양한 소식과 이벤트를 확인하세요.', 'symbol': '🎉', 'body': '이벤트 화면 확인을 위한 샘플 안내입니다. 실제 참여 신청이나 혜택 지급은 제공하지 않습니다.', 'is_published': True, 'sort_order': 3}]:
        Event.objects.create(**values)

class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[migrations.CreateModel(
        name="Event",
        fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("title",models.CharField(max_length=200,verbose_name="제목")),
            ("tag",models.CharField(blank=True,max_length=50,verbose_name="배너 문구")),
            ("summary",models.CharField(max_length=300,verbose_name="요약")),
            ("body",models.TextField(max_length=10000,verbose_name="내용")),
            ("symbol",models.CharField(default="🎁",max_length=8,verbose_name="표시 아이콘")),
            ("is_published",models.BooleanField(default=False,verbose_name="게시")),
            ("sort_order",models.PositiveIntegerField(default=0,verbose_name="표시 순서")),
        ], options={"verbose_name":"이벤트","verbose_name_plural":"이벤트","ordering":["sort_order","pk"]}
    ),migrations.RunPython(seed,migrations.RunPython.noop)]

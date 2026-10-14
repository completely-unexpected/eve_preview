from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(
        name='Game',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=100, verbose_name='게임명')),
            ('slug', models.SlugField(help_text='영문 소문자, 숫자, 하이픈과 밑줄로 입력하세요. 기존 링크 유지를 위해 등록 후 변경할 수 없습니다.', max_length=100, unique=True, verbose_name='주소 이름')),
            ('english_name', models.CharField(blank=True, max_length=100, verbose_name='영문명')),
            ('category', models.CharField(choices=[('ball','볼 게임'),('ladder','사다리'),('cards','카드 게임'),('sports','스포츠')], max_length=16, verbose_name='분류')),
            ('symbol', models.CharField(default='🎮', max_length=8, verbose_name='표시 아이콘')),
            ('description', models.TextField(blank=True, max_length=10000, verbose_name='게임 안내')),
            ('is_published', models.BooleanField(default=False, verbose_name='게시')),
            ('sort_order', models.PositiveIntegerField(default=0, help_text='숫자가 작은 게임부터 표시됩니다.', verbose_name='표시 순서')),
        ],
        options={'verbose_name':'게임','verbose_name_plural':'게임','ordering':['sort_order','pk']},
    )]

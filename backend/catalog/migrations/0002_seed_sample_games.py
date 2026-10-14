from django.db import migrations

def seed(apps, schema_editor):
    Game = apps.get_model("catalog", "Game")
    for values in [{'slug': 'powerball', 'name': '파워볼', 'english_name': 'POWERBALL', 'symbol': '🎱', 'category': 'ball', 'is_published': True, 'sort_order': 0}, {'slug': 'ladder', 'name': '사다리', 'english_name': 'LADDER', 'symbol': '🪜', 'category': 'ladder', 'is_published': True, 'sort_order': 1}, {'slug': 'cards', 'name': '카드 게임', 'english_name': 'CARD GAME', 'symbol': '♠', 'category': 'cards', 'is_published': True, 'sort_order': 2}, {'slug': 'token', 'name': '토큰 게임', 'english_name': 'TOKEN GAME', 'symbol': '🪙', 'category': 'ball', 'is_published': True, 'sort_order': 3}, {'slug': 'virtual', 'name': '가상 스포츠', 'english_name': 'VIRTUAL SPORTS', 'symbol': '⚽', 'category': 'sports', 'is_published': True, 'sort_order': 4}, {'slug': 'table', 'name': '테이블 게임', 'english_name': 'TABLE GAME', 'symbol': '🃏', 'category': 'cards', 'is_published': True, 'sort_order': 5}, {'slug': 'golden', 'name': '골든볼', 'english_name': 'GOLDEN BALL', 'symbol': '🔮', 'category': 'ball', 'is_published': True, 'sort_order': 6}, {'slug': 'powerladder', 'name': '파워 사다리', 'english_name': 'POWER LADDER', 'symbol': '🪜', 'category': 'ladder', 'is_published': True, 'sort_order': 7}, {'slug': 'starladder', 'name': '스타 사다리', 'english_name': 'STAR LADDER', 'symbol': '⭐', 'category': 'ladder', 'is_published': True, 'sort_order': 8}, {'slug': 'starball', 'name': '스타 파워볼', 'english_name': 'STAR POWERBALL', 'symbol': '🎱', 'category': 'ball', 'is_published': True, 'sort_order': 9}, {'slug': 'holdem', 'name': '홀덤', 'english_name': 'HOLDEM', 'symbol': '♣', 'category': 'cards', 'is_published': True, 'sort_order': 10}, {'slug': 'next', 'name': '넥스트 게임', 'english_name': 'NEXT GAME', 'symbol': '🎲', 'category': 'ball', 'is_published': True, 'sort_order': 11}]:
        slug = values.pop("slug")
        Game.objects.get_or_create(slug=slug, defaults=values)

class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

from django.db import migrations


def seed(apps, schema_editor):
    Game = apps.get_model('catalog', 'Game')
    for slug, name, english, symbol, order in [
        ('mgm-baccarat', 'MGM 바카라', 'MGM BACCARAT', '♠', 12),
        ('mgm-gostop', 'MGM 고스톱', 'MGM GOSTOP', '🎴', 13),
    ]:
        Game.objects.using(schema_editor.connection.alias).get_or_create(
            slug=slug, defaults=dict(name=name, english_name=english, symbol=symbol,
                category='cards', is_published=True, sort_order=order,
                description='OZ Live 공식 영상 중계'))


class Migration(migrations.Migration):
    dependencies = [('catalog', '0002_seed_sample_games')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

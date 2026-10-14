from django.db import migrations


def seed_level(apps, schema_editor):
    Level = apps.get_model("accounts", "MemberLevel")
    User = apps.get_model("accounts", "User")
    db = schema_editor.connection.alias
    Level.objects.using(db).get_or_create(number=1, defaults={"name": "기본"})
    User.objects.using(db).filter(level__isnull=True).update(level_id=1)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_user_multi_max_user_multi_min_user_multi_payout_and_more")]
    operations = [migrations.RunPython(seed_level, migrations.RunPython.noop)]

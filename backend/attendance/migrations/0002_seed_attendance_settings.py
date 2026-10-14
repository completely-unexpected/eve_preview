from django.db import migrations


def seed_settings(apps, schema_editor):
    Settings = apps.get_model("attendance", "AttendanceSettings")
    Settings.objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("attendance", "0001_initial")]
    operations = [migrations.RunPython(seed_settings, migrations.RunPython.noop)]

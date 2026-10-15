from django.db import migrations


def backfill(apps, schema_editor):
    Slip = apps.get_model('sportsfeed', 'DemoSlip')
    Leg = apps.get_model('sportsfeed', 'DemoLeg')
    alias = schema_editor.connection.alias
    for slip in Slip.objects.using(alias).all().iterator():
        Leg.objects.using(alias).bulk_create([
            Leg(slip_id=slip.pk, position=i, selection=selection)
            for i, selection in enumerate(slip.legs)
        ], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [('sportsfeed', '0003_demoslip_credited_amount_demoslip_settled_at_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]

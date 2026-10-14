from django.db import migrations


def seed_bonuses(apps, schema_editor):
    Bonus = apps.get_model("wallet", "DepositBonus")
    options = [
        {"name": "입금 보너스 10%", "bonus_percent": "10.00", "description": "카지노 이용불가", "sports_single": 300, "sports_double": 100, "sports_multi": 100, "minigame": 400, "casino": None, "sort_order": 10},
        {"name": "입금 보너스 5%", "bonus_percent": "5.00", "description": "카지노 이용불가", "sports_single": 100, "sports_double": 100, "sports_multi": 100, "minigame": 200, "casino": None, "sort_order": 20},
        {"name": "스포츠 멀티 보너스 15%", "bonus_percent": "15.00", "description": "스포츠 멀티 조건 안내", "sports_single": None, "sports_double": None, "sports_multi": 300, "minigame": None, "casino": None, "sort_order": 30},
        {"name": "보너스를 선택하지 않음", "bonus_percent": "0.00", "sports_single": 100, "sports_double": 100, "sports_multi": 100, "minigame": 100, "casino": 100, "sort_order": 99},
    ]
    for option in options:
        name = option.pop("name")
        Bonus.objects.using(schema_editor.connection.alias).get_or_create(name=name, defaults=option)


class Migration(migrations.Migration):
    dependencies = [("wallet", "0003_depositrequest_withdrawalrequest_and_more")]
    operations = [migrations.RunPython(seed_bonuses, migrations.RunPython.noop)]

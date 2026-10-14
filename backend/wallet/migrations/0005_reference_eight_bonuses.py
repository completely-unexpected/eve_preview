from django.db import migrations


def match_reference(apps, schema_editor):
    Bonus = apps.get_model("wallet", "DepositBonus")
    db = schema_editor.connection.alias
    options = [
        ("무제한 충전보너스 10%", "동일 경기 조합 베팅 불가능", "10.00", "입금 보너스 10%", [300, 100, 100, 400, None]),
        ("무제한 충전보너스 5%", "카지노 이용 불가", "5.00", "입금 보너스 5%", [100, 100, 100, 200, None]),
        ("무제한 충전보너스 15%", "단폴더, 두폴더, 카지노, 미니게임 이용 불가", "15.00", "스포츠 멀티 보너스 15%", [None, None, 300, None, None]),
        ("신규 입플 보너스", "단폴더, 2폴더, 카지노, 미니게임 이용불가", None, None, [None, None, 100, None, None]),
        ("신규회원 슬롯 전용 충전보너스 20%", "슬롯만 이용 가능", "20.00", None, [None, None, None, None, 100]),
        ("카지노 무제한 충전보너스 3%", "[이용 불가능] 스포츠 단폴더, 카지노 슬롯", "3.00", None, [None, 100, 100, 100, 100]),
        ("슬롯 전용 충전보너스", "카지노 슬롯만 이용 가능", None, None, [None, None, None, None, 100]),
        ("보너스를 선택하지 않음", "", "0.00", "보너스를 선택하지 않음", [100, 100, 100, 100, 100]),
    ]
    selected = []
    categories = ["sports_single", "sports_double", "sports_multi", "minigame", "casino"]
    for index, (name, description, percent, previous, rolling) in enumerate(options, 1):
        record = Bonus.objects.using(db).filter(name=name).first()
        if record is None and previous:
            record = Bonus.objects.using(db).filter(name=previous).first()
        new = record is None
        if new:
            record = Bonus()
        record.name = name
        record.description = description
        record.is_active = True
        record.sort_order = index * 10
        if percent is not None:
            record.bonus_percent = percent
        elif new:
            record.bonus_percent = 0
        if new:
            for key, value in zip(categories, rolling):
                setattr(record, key, value)
        record.save(using=db)
        selected.append(record.pk)
    Bonus.objects.using(db).exclude(pk__in=selected).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("wallet", "0004_seed_deposit_bonuses")]
    operations = [migrations.RunPython(match_reference, migrations.RunPython.noop)]

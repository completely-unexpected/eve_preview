from django.db import migrations, models
from django.utils import timezone


def preserve_existing_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.using(schema_editor.connection.alias).filter(is_active=False).update(
        account_status="suspended", session_revoked_at=timezone.now(),
    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="user", name="account_status",
            field=models.CharField(
                choices=[("pending", "승인 대기"), ("approved", "승인 완료"), ("suspended", "이용 정지")],
                default="approved", max_length=16, verbose_name="가입 상태",
            ),
        ),
        migrations.AddField(
            model_name="user", name="session_revoked_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(preserve_existing_accounts, migrations.RunPython.noop),
    ]

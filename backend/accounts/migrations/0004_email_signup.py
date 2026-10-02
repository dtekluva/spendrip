from django.db import migrations, models


def blank_emails_to_null(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(email="").update(email=None)
    # Lower-case the rest so lookups match; drop duplicates' emails rather than fail the migration.
    seen = set()
    for u in User.objects.exclude(email=None).order_by("pk"):
        e = u.email.strip().lower()
        u.email = None if e in seen or e.endswith(".local") else e
        seen.add(e)
        u.save(update_fields=["email"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_waitlistentry")]

    operations = [
        migrations.AlterField("user", "email", models.EmailField(max_length=254, null=True, blank=True)),
        migrations.RunPython(blank_emails_to_null, migrations.RunPython.noop),
        migrations.AlterField("user", "email", models.EmailField(max_length=254, unique=True, null=True, blank=True)),
        migrations.AddField("user", "kyc_id_type", models.CharField(max_length=3, default="nin")),
        migrations.RenameModel("PhoneOtp", "OneTimeCode"),
        migrations.RenameField("onetimecode", "phone", "target"),
        migrations.AlterField("onetimecode", "target", models.CharField(max_length=254, db_index=True)),
    ]

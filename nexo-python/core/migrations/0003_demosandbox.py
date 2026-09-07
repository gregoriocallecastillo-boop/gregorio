from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_immutable_history")]
    operations = [migrations.CreateModel(
        name="DemoSandbox",
        fields=[
            ("token_hash", models.CharField(max_length=64, primary_key=True, serialize=False)),
            ("data", models.JSONField(default=dict)),
            ("expires_at", models.DateTimeField(db_index=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ],
    )]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_config_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organization",
            name="management_server",
            field=models.CharField(default="http://127.0.0.1:20721", max_length=255, verbose_name="HTTP 地址"),
        ),
        migrations.AlterField(
            model_name="organization",
            name="management_server_grpc",
            field=models.CharField(default="http://127.0.0.1:20722", max_length=255, verbose_name="gRPC 地址"),
        ),
    ]

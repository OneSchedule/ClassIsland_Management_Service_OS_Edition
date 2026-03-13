from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="management_server",
            field=models.CharField(default="http://127.0.0.1:8000", max_length=255, verbose_name="HTTP 地址"),
        ),
        migrations.AddField(
            model_name="organization",
            name="management_server_grpc",
            field=models.CharField(default="http://127.0.0.1:50051", max_length=255, verbose_name="gRPC 地址"),
        ),
    ]

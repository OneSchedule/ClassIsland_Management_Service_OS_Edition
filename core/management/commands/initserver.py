"""
初始化集控服务器 —— 创建默认组织、生成密钥、创建超级用户。
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from core.models import Organization
from core.crypto import generate_server_keypair, get_active_keypair


class Command(BaseCommand):
    help = "初始化 ClassIsland 集控服务器（创建组织、密钥、管理员）"

    def add_arguments(self, parser):
        parser.add_argument("--org-name", type=str, default="ClassIsland 集控")
        parser.add_argument("--admin-user", type=str, default="admin")
        parser.add_argument("--admin-pass", type=str, default="admin")

    def handle(self, *args, **options):
        org_name = options["org_name"]
        admin_user = options["admin_user"]
        admin_pass = options["admin_pass"]

        # 创建组织
        org, created = Organization.objects.get_or_create(
            defaults={"name": org_name}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"已创建组织: {org.name}"))
        else:
            self.stdout.write(f"组织已存在: {org.name}")

        # 生成密钥
        keypair = get_active_keypair(org)
        if keypair is None:
            keypair = generate_server_keypair(org)
            self.stdout.write(self.style.SUCCESS(f"已生成 PGP 密钥对, Key ID: {keypair.key_id}"))
        else:
            self.stdout.write(f"密钥已存在, Key ID: {keypair.key_id}")

        # 创建管理员
        if not User.objects.filter(username=admin_user).exists():
            User.objects.create_superuser(admin_user, "", admin_pass)
            self.stdout.write(self.style.SUCCESS(
                f"已创建管理员: {admin_user} / {admin_pass}"
            ))
        else:
            self.stdout.write(f"管理员 {admin_user} 已存在")

        self.stdout.write(self.style.SUCCESS("\n初始化完成！"))
        self.stdout.write(f"  HTTP: python manage.py runserver 0.0.0.0:8000")
        self.stdout.write(f"  gRPC: python manage.py grpcserver --port 50051")
        self.stdout.write(f"  管理面板: http://localhost:8000/")

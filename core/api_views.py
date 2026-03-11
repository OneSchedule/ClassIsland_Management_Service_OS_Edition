"""
REST API 视图 —— 供 ClassIsland 客户端拉取清单和资源。
无需认证（客户端以 client_uid 为标识）。
"""
from django.http import JsonResponse, Http404
from django.views import View
from django.conf import settings

from core.models import Client, ClassGroup, Organization


class ClientManifestView(View):
    """
    GET /api/v1/client/{cuid}/manifest
    返回 ManagementManifest JSON。
    """

    def get(self, request, cuid):
        org = Organization.objects.first()
        if org is None:
            return JsonResponse({"error": "服务器未初始化"}, status=500)

        # 查找客户端及其班级组
        try:
            client = Client.objects.select_related("class_group").get(client_uid=cuid)
        except Client.DoesNotExist:
            return JsonResponse({"error": "客户端未注册"}, status=404)

        group = client.class_group
        host = request.build_absolute_uri("/").rstrip("/")

        def _source(resource_path: str, version: int):
            return {
                "value": f"{host}{resource_path}" if version > 0 else "",
                "version": version,
            }

        if group:
            gid = group.class_identity
            manifest = {
                "classPlanSource": _source(
                    f"/api/v1/objects/{gid}/classplans.json",
                    group.class_plans_version,
                ),
                "timeLayoutSource": _source(
                    f"/api/v1/objects/{gid}/timelayouts.json",
                    group.time_layouts_version,
                ),
                "subjectsSource": _source(
                    f"/api/v1/objects/{gid}/subjects.json",
                    group.subjects_version,
                ),
                "defaultSettingsSource": _source(
                    f"/api/v1/objects/{gid}/settings.json",
                    group.settings_version,
                ),
                "policySource": _source(
                    f"/api/v1/objects/{gid}/policy.json",
                    group.policy_version,
                ),
                "componentsSource": _source(
                    f"/api/v1/objects/{gid}/components.json",
                    group.components_version,
                ),
                "credentialSource": _source(
                    f"/api/v1/objects/{gid}/credentials.json",
                    group.credential_version,
                ),
            }
        else:
            # 未分配班级组 —— 返回空资源
            empty = {"value": "", "version": 0}
            manifest = {
                "classPlanSource": empty,
                "timeLayoutSource": empty,
                "subjectsSource": empty,
                "defaultSettingsSource": empty,
                "policySource": empty,
                "componentsSource": empty,
                "credentialSource": empty,
            }

        manifest["serverKind"] = 1  # ManagementServer
        manifest["organizationName"] = org.name
        manifest["coreVersion"] = org.core_version

        return JsonResponse(manifest)


class ResourceView(View):
    """
    GET /api/v1/objects/{class_identity}/{resource_type}.json
    返回班级组的具体资源 JSON。
    """
    RESOURCE_MAP = {
        "classplans": "class_plans_json",
        "timelayouts": "time_layouts_json",
        "subjects": "subjects_json",
        "settings": "settings_json",
        "policy": "policy_json",
        "components": "components_json",
        "credentials": "credential_json",
    }

    def get(self, request, class_identity, resource_type):
        field = self.RESOURCE_MAP.get(resource_type)
        if field is None:
            raise Http404("未知资源类型")

        try:
            group = ClassGroup.objects.get(class_identity=class_identity)
        except ClassGroup.DoesNotExist:
            raise Http404("班级组不存在")

        data = getattr(group, field, {})
        return JsonResponse(data, safe=False)

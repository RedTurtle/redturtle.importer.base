# -*- coding: utf-8 -*-
from plone import api
from redturtle.importer.base.interfaces import IPostMigrationStep
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface

import requests
import logging

logger = logging.getLogger(__name__)


@adapter(Interface, Interface)
@implementer(IPostMigrationStep)
class ImportUsersAndGroups(object):
    order = 5

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, transmogrifier):
        """
        """
        section = transmogrifier.get("users_and_groups")
        if section is None or not self.should_execute(transmogrifier):
            return
        logger.info("## Import users and groups ##")
        import_users = self.get_boolean_value(
            section=section, name="import-users"
        )
        import_groups = self.get_boolean_value(
            section=section, name="import-groups"
        )
        if import_users:
            self.import_users(transmogrifier=transmogrifier)
        if import_groups:
            self.import_groups(transmogrifier=transmogrifier)

    def get_boolean_value(self, section, name):
        value = section.get(name, "false").lower()
        return value == "true" or value == "1"

    def import_users(self, transmogrifier):
        json_data = self.retrieve_json_from_remote(
            transmogrifier=transmogrifier, view_name="export_users"
        )
        if not json_data:
            return
        if "_acl_users" not in json_data:
            logger.warning(
                "Unable to import users: data format not correct: {}".format(
                    json_data
                )
            )
            return
        for userid, data in json_data["_acl_users"].items():
            user = api.user.get(username=userid)
            roles = data["roles"]
            # remove these roles, they cannot be granted
            if "Authenticated" in data["roles"]:
                roles.remove("Authenticated")
            if "Anonymous" in data["roles"]:
                roles.remove("Anonymous")
            if not data["email"]:
                data["email"] = "user@site.com"
            if user:
                api.user.grant_roles(username=userid, roles=roles)
                continue
            try:
                user = api.user.create(
                    username=userid,
                    email=data["email"],
                    properties=data.get("properties", {}),
                )
                api.user.grant_roles(username=userid, roles=roles)
            except ValueError as e:
                logger.warn(
                    "Import User '{0}' threw an error: {1}".format(userid, e)
                )

    def import_groups(self, transmogrifier):
        json_data = self.retrieve_json_from_remote(
            transmogrifier=transmogrifier, view_name="export_groups"
        )
        if not json_data:
            return
        if "_acl_groups" not in json_data:
            logger.warning(
                "Unable to import groups: data format not correct: {}".format(
                    json_data
                )
            )
            return
        group_tool = api.portal.get_tool(name="portal_groups")
        for groupid, props in json_data["_acl_groups"].items():
            acl_group = api.group.get(groupname=groupid)
            if not acl_group:
                acl_group = api.group.create(
                    groupname=groupid,
                    title=props["title"],
                    description=props["description"],
                    roles=props["roles"],
                )
            else:
                group_tool.editGroup(
                    groupid,
                    roles=props["roles"],
                    title=props["title"],
                    description=props["description"],
                )
            for member in props["members"]:
                acl_group.addMember(member)

    def retrieve_json_from_remote(self, transmogrifier, view_name):
        section = transmogrifier.get("catalogsource")
        url = section.get("remote-url", "")
        root = section.get("remote-root", "")
        if not url or not root:
            logger.warning(
                "Unable to call remote for retrieving {view_name}. Missing remote-url or remote-root in configuration.".format(  # noqa
                    view_name=view_name
                )
            )
            return
        url = "{url}{root}/{view_name}".format(
            url=section.get("remote-url"),
            root=section.get("remote-root"),
            view_name=view_name,
        )
        resp = requests.get(
            url,
            auth=(
                section.get("remote-username"),
                section.get("remote-password"),
            ),
        )
        if resp.ok and resp.status_code == 200:
            return resp.json()
        logger.warning(
            "Unable to call {url}: {reason} ({code})".format(
                url=url, reason=resp.reason, code=resp.status_code
            )
        )

    def should_execute(self, transmogrifier):
        section = transmogrifier.get("catalogsource")
        flag = section.get("disable-post-scripts", "False").lower()
        return flag == "false" or flag == 0

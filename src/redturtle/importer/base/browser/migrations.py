# -*- coding: utf-8 -*-
from __future__ import print_function
from AccessControl import Unauthorized
from Acquisition import aq_base
from redturtle.importer.base.transmogrifier.transmogrifier import (
    Transmogrifier,
)
from lxml import etree
from plone import api
from plone.app.textfield import RichText
from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import iterSchemata
from plone.memoize.view import memoize
from plone.outputfilters.filters.resolveuid_and_caption import resolveuid_re
from Products.Five.browser import BrowserView
from redturtle.importer.base import logger
from redturtle.importer.base.interfaces import IDeserializer
from redturtle.importer.base.transmogrifier.utils import (
    get_additional_config,
    get_transmogrifier_configuration,
)
from zope.component import queryMultiAdapter
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldsInOrder

import json
import requests
import six
import os

# import errno


class RedTurtlePlone5MigrationMain(BrowserView):
    """
    Migration view
    """

    transmogrifier = None
    transmogrifier_conf = "redturtlePlone5Main"
    skip_types_in_link_check = ["Discussion Item"]

    def __call__(self):
        if not self.request.form.get("confirm", False):
            return self.index()

        return self.do_migrate()

    def fix_relation(self):
        # nel transmogrifier c'e' una lista di tuple:
        # (path, fieldname, value) per le quali vanno rifatte le relations
        logger.info("Fix Relations.")
        for (path, fieldname, value) in getattr(
            self.transmogrifier, "fixrelations", []
        ):
            if not value:
                continue
            obj = api.content.get(path)
            if not obj:
                logger.warning(
                    "[FIX RELATIONS] - Unable to find {path}. No relations fixed.".format(  # noqa
                        path=path
                    )
                )
                continue
            logger.info("fix {0} {1} {2}".format(path, fieldname, value))
            for schemata in iterSchemata(obj):
                for name, field in getFieldsInOrder(schemata):
                    if name == fieldname:
                        if isinstance(value, six.string_types):
                            value = uuidToObject(value)
                        else:
                            value = [uuidToObject(uuid) for uuid in value]
                        deserializer = queryMultiAdapter(
                            (field, obj), IDeserializer
                        )
                        value = deserializer(
                            value, [], {}, True, logger=logger
                        )
                        # self.disable_constraints,
                        # logger=self.log,
                        field.set(field.interface(obj), value)
                        notify(ObjectModifiedEvent(obj))

    def fix_defaultPages(self):
        logger.info("Fix Default Pages.")
        for item in getattr(self.transmogrifier, "default_pages", []):
            try:
                obj = api.content.get(UID=item["obj"])
                obj.manage_addProperty(
                    "default_page", item["default_page"], "string"
                )
                obj.reindexObject(["is_default_page"])
            except Exception:
                pass

    def do_migrate(self, REQUEST=None):

        authenticator = api.content.get_view(
            context=api.portal.get(),
            request=self.request,
            name=u"authenticator",
        )
        if not authenticator.verify():
            raise Unauthorized

        portal = api.portal.get()
        self.transmogrifier = Transmogrifier(portal)
        # self.cleanup_log_files()
        self.transmogrifier(
            configuration_id=self.transmogrifier_conf,
            **get_additional_config()
        )

        # run scripts after migration
        self.scripts_post_migration()
        logger.info("Migration done.")
        api.portal.show_message(
            message="Migration done. Check logs for a complete report."
            "Scripts after migration running....",
            request=self.request,
        )
        return self.request.response.redirect(
            "{0}/migration-results".format(api.portal.get().absolute_url())
        )

    def scripts_post_migration(self):
        self.fix_relation()
        self.fix_defaultPages()
        self.generate_broken_links_list()
        self.fix_link_noreference()
        self.import_users_and_groups()

    # def cleanup_log_files(self):
    #     for type, section in [("in", "catalogsource"), ("out", "results")]:
    #         additional_config = get_additional_config(section=section)
    #         config = get_base_config(section=section)
    #         config.update(additional_config)
    #         file_name = config.get(
    #             "file-name-{0}".format(type),
    #             "migration_content_{0}.json".format(type),
    #         )
    #         file_path = "{0}/{1}_{2}".format(
    #             config.get("migration-dir"),
    #             api.portal.get().getId(),
    #             file_name,
    #         )
    #         try:
    #             os.remove(file_path)
    #         except OSError as e:
    #             if e.errno != errno.ENOENT:
    #                 # re-raise exception if a different error occurred
    #                 raise

    def get_config(self):
        return get_transmogrifier_configuration()

    def generate_broken_links_list(self):
        logger.info("Generating broken tinymce internal links.")
        pc = api.portal.get_tool(name="portal_catalog")
        brains = pc()
        broken_urls = []

        for brain in brains:
            if brain.portal_type in self.skip_types_in_link_check:
                continue
            item = aq_base(brain.getObject())
            for schemata in iterSchemata(item):
                for name, field in getFieldsInOrder(schemata):
                    if not isinstance(field, RichText):
                        continue
                    item_field = getattr(item, name, None)
                    if not item_field:
                        continue
                    raw_text = item_field.raw
                    if not raw_text:
                        continue
                    try:
                        xml = etree.HTML(raw_text)
                    except ValueError:
                        # text is not html (probably an svg)
                        continue
                    for link in xml.xpath("//a"):
                        match = resolveuid_re.match(link.get("href", ""))
                        if not match:
                            continue
                        uid, _subpath = match.groups()
                        obj = api.content.get(UID=uid[:32])
                        if not obj:
                            url = brain.getURL()
                            if url not in broken_urls:
                                broken_urls.append(url)
        self.write_broken_links(broken_urls)

    def write_broken_links(self, paths):
        section = self.transmogrifier.get("results")
        if section is None:
            logger.warning(
                '"results" section not found in transmogrifier configuration.'
                " Unable to write broken links file."
            )
            return
        file_name = section.get("broken-links-tiny")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        with open(file_path, "w") as fp:
            json.dump(paths, fp)

    def check_link_exist(self, link, link_path):
        result = True
        section = self.transmogrifier.get("catalogsource")
        remote_site = section.get("remote-root")
        try:
            if remote_site not in link_path:
                return True
        except Exception:
            if not link.internal_link.to_id:
                return False
            return True

        link_to_check_path = "%s" % (link_path.split(remote_site)[1])
        if not api.content.get(path=link_to_check_path):
            result = False
        return result

    def fix_link_noreference(self):
        logger.info("Generating noreference links.")
        noreference_urls = []
        portal_id = api.portal.get().getId()
        brains = api.content.find(portal_type="Link")
        logger.info("Found {0} items.".format(len(brains)))

        for brain in brains:
            remote_url = brain.getRemoteUrl
            if not remote_url:
                continue
            if "resolveuid" not in remote_url:
                continue
            uid = brain.getRemoteUrl.replace(
                "/{0}/resolveuid/".format(portal_id), ""
            )
            if not api.content.find(UID=uid):
                link = brain.getObject()
                noreference_urls.append(link.absolute_url())
                logger.warn("Removing {0}".format(link.absolute_url()))
                try:
                    api.content.delete(obj=link, check_linkintegrity=False)
                except KeyError:
                    logger.debug(
                        "Cannot remove {0}".format(link.absolute_url())
                    )

        self.write_noreference_links(noreference_urls)

    def write_noreference_links(self, paths):
        section = self.transmogrifier.get("results")
        file_name = section.get("noreference-links")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        with open(file_path, "w") as fp:
            json.dump(paths, fp)

    def import_users_and_groups(self):
        section = self.transmogrifier.get("users_and_groups")
        if section is None:
            return
        logger.info("-- Import users and groups from file --")
        import_users = self.get_boolean_value(
            section=section, name="import-users"
        )
        import_groups = self.get_boolean_value(
            section=section, name="import-groups"
        )
        if import_users:
            self.import_users()
        if import_groups:
            self.import_groups()

    def get_boolean_value(self, section, name):
        value = section.get(name, "false").lower()
        return value == "true" or value == "1"

    def retrieve_json_from_remote(self, view_name):
        section = self.transmogrifier.get("catalogsource")
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

    def import_users(self):
        json_data = self.retrieve_json_from_remote(view_name="export_users")
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

    def import_groups(self):
        json_data = self.retrieve_json_from_remote(view_name="export_groups")
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


class MigrationResults(BrowserView):
    """
    read debug files and expose statistics
    """

    @property
    @memoize
    def transmogrifier_conf(self):
        return get_transmogrifier_configuration()

    def get_results(self):

        in_json = self.get_json_data(
            option="file-name-in", section_id="catalogsource"
        )
        out_json = self.get_json_data(
            option="file-name-out", section_id="results"
        )

        results = {
            "in_count": len(list(in_json.keys())),
            "out_count": len(list(out_json.keys())),
            "broken_links": self.get_broken_links(),
            "noreference_links": self.get_noreference_links(),
        }

        if list(out_json.keys()) == list(in_json.keys()):
            results["same_results"] = True
        else:
            results["same_results"] = False
            results["not_migrated"] = self.generate_not_migrated_list(
                in_json=in_json, out_json=out_json
            )

        return results

    def generate_not_migrated_list(self, in_json, out_json):
        diff_keys = set(in_json.keys()) - set(out_json.keys())
        return [in_json[k] for k in diff_keys]

    def get_json_data(self, option, section_id):
        config = self.transmogrifier_conf
        section = config.get(section_id, None)
        file_name = section.get(option, "")
        if not file_name:
            return []
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                return json.loads(fp.read())
        else:
            return {}

    def get_broken_links(self):
        config = self.transmogrifier_conf
        section = config.get("results", None)
        file_name = section.get("broken-links-tiny")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                return json.loads(fp.read())
        else:
            return []

    def get_noreference_links(self):
        config = self.transmogrifier_conf
        section = config.get("results", None)
        file_name = section.get("noreference-links")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                return json.loads(fp.read())
        else:
            return []

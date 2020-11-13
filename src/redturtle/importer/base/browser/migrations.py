# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from Acquisition import aq_base
from lxml import etree
from plone import api
from plone.app.textfield import RichText
from plone.dexterity.utils import iterSchemata
from plone.memoize.view import memoize
from plone.outputfilters.filters.resolveuid_and_caption import resolveuid_re
from Products.Five.browser import BrowserView
from redturtle.importer.base import logger
from redturtle.importer.base.interfaces import IPostMigrationStep
from plone.outputfilters.browser.resolveuid import uuidToObject
from redturtle.importer.base.transmogrifier.transmogrifier import (
    Transmogrifier,
)
from redturtle.importer.base.transmogrifier.utils import get_additional_config
from redturtle.importer.base.transmogrifier.utils import (
    get_transmogrifier_configuration,
)
from zope.component import subscribers
from zope.schema import getFieldsInOrder

import json
import os
import re


class RedTurtlePlone5MigrationMain(BrowserView):
    """
    Migration view
    """

    transmogrifier = None
    transmogrifier_conf = "redturtlePlone5Main"

    def __call__(self):
        if not self.request.form.get("confirm", False):
            return self.index()

        return self.do_migrate()

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
        """
        Excecute a series of post migration steps in order
        """
        handlers = [
            x
            for x in subscribers(
                (self.context, self.request), IPostMigrationStep
            )
        ]
        for handler in sorted(handlers, key=lambda h: h.order):
            handler(transmogrifier=self.transmogrifier)

    def get_config(self):
        return get_transmogrifier_configuration()


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
        file_name = section.get("broken-links")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        if self.request.form.get("load-links", ""):
            logger.info("## Generating broken links list ##")
            self.generate_broken_links_list(file_path=file_path)
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                return json.loads(fp.read())
        else:
            return []

    def generate_broken_links_list(self, file_path):
        pc = api.portal.get_tool(name="portal_catalog")
        brains = list(pc())
        broken_urls = []
        skip_types_in_link_check = ["Discussion Item"]

        for i, brain in enumerate(brains):
            if (i + 1) % 200 == 0:
                logger.info(" - Progress {}/{}".format(i + 1, len(brains)))
            if brain.portal_type in skip_types_in_link_check:
                continue
            item = aq_base(brain.getObject())
            has_broken = False
            for schemata in iterSchemata(item):
                for name, field in getFieldsInOrder(schemata):
                    if not isinstance(field, RichText):
                        if name == "blocks":
                            has_broken = self.check_broken_blocks_links(
                                blocks=getattr(item, name, None)
                            )
                        else:
                            continue
                    else:
                        item_field = getattr(item, name, None)
                        if not item_field:
                            continue
                        try:
                            html = item_field.raw
                        except AttributeError:
                            continue
                        if not html:
                            continue
                        has_broken = self.check_broken_text_links(html=html)
                    if has_broken:
                        url = brain.getURL()
                        if url not in broken_urls:
                            broken_urls.append(url)
                if has_broken:
                    break

        with open(file_path, "w") as fp:
            json.dump(broken_urls, fp)

    def check_broken_text_links(self, html):
        try:
            xml = etree.HTML(html)
        except ValueError:
            # text is not html (probably an svg)
            return False
        for link in xml.xpath("//a"):
            href = link.get("href", "")
            if href.startswith("http"):
                #  skip external links
                continue
            match = resolveuid_re.match(href)
            if not match:
                continue
            uid, _subpath = match.groups()
            obj = api.content.get(UID=uid[:32])
            if not obj:
                return True
        return False

    def check_broken_blocks_links(self, blocks):
        for value in blocks.values():
            entity_map = value.get("text", {}).get("entityMap", {})
            for entity in entity_map.values():
                if entity.get("type") != "LINK":
                    continue
                href = entity.get("data", {}).get("href", "")
                url = entity.get("data", {}).get("url", "")
                RESOLVEUID_RE = re.compile(
                    "^[./]*resolve[Uu]id/([^/]*)/?(.*)$"
                )
                MAIL_RE = r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$"
                for path in [href, url]:
                    if not path:
                        continue
                    if (
                        path.startswith("http")
                        or path.startswith("www")
                        or path.startswith("mailto")
                        or re.search(MAIL_RE, path)
                    ):
                        #  skip external links and emails
                        continue
                    match = RESOLVEUID_RE.match(path)
                    if match is None:
                        return True
                    uid, suffix = match.groups()
                    if not uuidToObject(uid):
                        return True
        return False

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

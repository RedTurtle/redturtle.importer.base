# -*- coding: utf-8 -*-
from Acquisition import aq_base
from lxml import etree
from plone import api
from plone.app.textfield import RichText
from plone.dexterity.utils import iterSchemata
from plone.outputfilters.filters.resolveuid_and_caption import resolveuid_re
from redturtle.importer.base.interfaces import IPostMigrationStep
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from zope.schema import getFieldsInOrder

import json
import logging

logger = logging.getLogger(__name__)


@adapter(Interface, Interface)
@implementer(IPostMigrationStep)
class GenerateBrokenLinks(object):
    order = 3

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, transmogrifier):
        """
        """
        if not self.should_execute(transmogrifier):
            return
        logger.info("## Generating broken tinymce internal links ##")
        pc = api.portal.get_tool(name="portal_catalog")
        brains = pc()
        broken_urls = []
        skip_types_in_link_check = ["Discussion Item"]

        for brain in brains:
            if brain.portal_type in skip_types_in_link_check:
                continue
            try:
                item = aq_base(brain.getObject())
            except:
                continue
            for schemata in iterSchemata(item):
                for name, field in getFieldsInOrder(schemata):
                    if not isinstance(field, RichText):
                        continue
                    item_field = getattr(item, name, None)
                    if not item_field:
                        continue
                    try:
                        raw_text = item_field.raw
                    except AttributeError:
                        continue
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
        self.write_broken_links(
            paths=broken_urls, transmogrifier=transmogrifier
        )

    def should_execute(self, transmogrifier):
        section = transmogrifier.get("catalogsource")
        flag = section.get("disable-post-scripts", "False").lower()
        return flag == "false" or flag == 0

    def write_broken_links(self, paths, transmogrifier):
        section = transmogrifier.get("results")
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

# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import IPostMigrationStep
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from plone import api

import logging


logger = logging.getLogger(__name__)


@adapter(Interface, Interface)
@implementer(IPostMigrationStep)
class FixDefaultPages(object):
    order = 2

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, transmogrifier):
        """
        """
        logger.info("## Fix Default Pages ##")
        for item in getattr(transmogrifier, "default_pages", []):
            try:
                obj = api.content.get(UID=item["obj"])
                obj.manage_addProperty(
                    "default_page", item["default_page"], "string"
                )
                obj.reindexObject(["is_default_page"])
            except Exception:
                pass

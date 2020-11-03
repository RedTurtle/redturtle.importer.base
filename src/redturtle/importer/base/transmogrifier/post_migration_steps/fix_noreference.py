# -*- coding: utf-8 -*-
from plone import api
from redturtle.importer.base.interfaces import IPostMigrationStep
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface

import json
import logging

logger = logging.getLogger(__name__)


@adapter(Interface, Interface)
@implementer(IPostMigrationStep)
class FixNoReferenceLinks(object):
    order = 4

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, transmogrifier):
        """
        """
        if not self.should_execute(transmogrifier):
            return
        logger.info("## Generating noreference links ##")
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

        self.write_noreference_links(
            paths=noreference_urls, transmogrifier=transmogrifier
        )

    def should_execute(self, transmogrifier):
        section = transmogrifier.get("catalogsource")
        flag = section.get("disable-post-scripts", "False").lower()
        return flag == "false" or flag == 0

    def write_noreference_links(self, paths, transmogrifier):
        section = transmogrifier.get("results")
        file_name = section.get("noreference-links")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        with open(file_path, "w") as fp:
            json.dump(paths, fp)

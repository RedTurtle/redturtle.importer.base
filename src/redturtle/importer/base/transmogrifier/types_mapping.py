# -*- coding: utf-8 -*-
from Products.CMFPlone.interfaces import IPloneSiteRoot
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from redturtle.importer.base.interfaces import IPortalTypeMapping

import logging

logger = logging.getLogger(__name__)


@adapter(IPloneSiteRoot, IBrowserRequest)
@implementer(IPortalTypeMapping)
class LinkMapping(object):
    order = 1

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, item, typekey):
        """
        """
        if item[typekey] == "Link":
            internal_link = item.get("internalLink", "")
            external_link = item.get("remoteUrl", "")
            if internal_link:
                item["remoteUrl"] = "${0}/resolveuid/{1}".format(
                    "{portal_url}", internal_link
                )
            elif external_link:
                item["remoteUrl"] = external_link
        return item


@adapter(IPloneSiteRoot, IBrowserRequest)
@implementer(IPortalTypeMapping)
class CollectionMapping(object):
    order = 2

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, item, typekey):
        """
        """
        portal_type = item[typekey]
        if portal_type == "Collection":
            if item.get("_layout", None):
                del item["_layout"]

            mapping = {
                "portal_type": "plone.app.querystring.operation.selection.any",
                "review_state": "plone.app.querystring.operation.selection.any",
            }
            query = item["query"]

            for criteria in query:
                # Fix query string opertaion
                proper_operation = mapping.get(criteria.get("i"))
                if proper_operation:
                    logger.info(
                        "Changed collection criteria for {0} from {1} to {2} for item: {3}".format(  # noqa
                            criteria.get("i"),
                            criteria.get("o"),
                            proper_operation,
                            item["_path"],
                        )
                    )
                    criteria.update({"o": proper_operation})
                # Fix path format if a uid is specified
                if "path" in list(criteria.values()):
                    path_value = criteria.get("v")
                    if "::" not in path_value:
                        continue
                    uid, number = path_value.split("::")
                    if uid:
                        fixed_uid = "{0}::-{1}".format(uid, number)
                        criteria.update({"v": fixed_uid})
        return item

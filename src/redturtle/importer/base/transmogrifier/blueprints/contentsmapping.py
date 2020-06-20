# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultKeys
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import Matcher
from redturtle.importer.base import logger
from zope.annotation.interfaces import IAnnotations
from zope.interface import provider
from zope.interface import implementer

import ast

ITEMS_IN = "redturtle.importer.base.items_in"


@implementer(ISection)
@provider(ISectionBlueprint)
class ContentsMappingSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        # read additional config in cfg file, and apply to default
        self.debug_infos = {}

        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if "path-key" in options:
            pathkeys = options["path-key"].splitlines()
        else:
            pathkeys = defaultKeys(options["blueprint"], name, "path")
        self.pathkey = Matcher(*pathkeys)

        self.typekey = defaultMatcher(
            options, "type-key", name, "type", ("portal_type", "Type")
        )

        if options.get("exclude-type", None):
            self.exclude_type = ast.literal_eval(
                options.get("exclude-type", None)
            )

        annotations = IAnnotations(self.context.REQUEST)
        self.items_in = annotations.setdefault(ITEMS_IN, {})

    def collection_mapping(self, item):
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

    def __iter__(self):
        for item in self.previous:
            keys = list(item.keys())
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]

            # integrazione check del tipo all'interno di questo ciclo
            skip = False
            if getattr(self, "exclude_type", None):
                for type in self.exclude_type:
                    # fathers type
                    if item.get("fathers_type_list", None):
                        for fathers_type in item["fathers_type_list"]:
                            if fathers_type == type:
                                skip = True
                                break
                            if skip:
                                break
                    else:
                        logger.warning(
                            "Item {0} doesn't have father".format(
                                item["_path"]
                            )
                        )
                    # check obj type
                    if item.get("_type", None):
                        if item["_type"] == type:
                            skip = True

            if skip:
                if item.get("_uid") in self.items_in:
                    self.items_in[item.get("_uid")][
                        'reason'
                    ] = 'Skipped portal_type'
                else:
                    self.items_in[item.get("_uid")] = {
                        "id": item.get("_id"),
                        "portal_type": item.get("_type"),
                        "title": item.get("title"),
                        "path": item.get("_path"),
                    }
                continue

            if not (typekey and pathkey):
                logger.warning("Not enough info for item: {0}".format(item))
                yield item
                continue

            if item[typekey] == "Topic":
                item[typekey] = "Collection"

                if item.get("_layout", None):
                    del item["_layout"]

                yield item
                continue

            elif item[typekey] == "Collection":
                item[typekey] = "Collection"

                if item.get("_layout", None):
                    del item["_layout"]

                self.collection_mapping(item)
                yield item
                continue

            elif item[typekey] == "Link":
                internal_link = item.get("internalLink", "")
                external_link = item.get("remoteUrl", "")
                if internal_link:
                    item["remoteUrl"] = "${0}/resolveuid/{1}".format(
                        "{portal_url}", internal_link
                    )
                elif external_link:
                    item["remoteUrl"] = external_link

                yield item
                continue

            else:
                yield item
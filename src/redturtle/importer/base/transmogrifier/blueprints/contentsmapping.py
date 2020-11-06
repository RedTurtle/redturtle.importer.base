# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import defaultMatcher
from redturtle.importer.base.transmogrifier.utils import Matcher
from redturtle.importer.base import logger
from zope.annotation.interfaces import IAnnotations
from zope.interface import provider
from zope.interface import implementer
from redturtle.importer.base.interfaces import IPortalTypeMapping
from zope.component import subscribers
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

    def __iter__(self):
        for item in self.previous:
            keys = list(item.keys())
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]

            # integrazione check del tipo all'interno di questo ciclo
            skip = False
            for excluded_type in getattr(self, "exclude_type", []):
                if skip:
                    break
                # if item is in a blacked-list type, skip it
                for parent_type in item.get("parents_type_list", []):
                    if parent_type == excluded_type:
                        skip = True
                        break
                    if skip:
                        break
                # check obj type
                if item.get("_type", None):
                    if item["_type"] == excluded_type:
                        skip = True
            if skip:
                if item.get("_uid") in self.items_in:
                    self.items_in[item.get("_uid")][
                        "reason"
                    ] = "Skipped portal_type"
                else:
                    self.items_in[item.get("_uid")] = {
                        "id": item.get("_id"),
                        "portal_type": item[typekey],
                        "title": item.get("title"),
                        "path": item.get("_path"),
                    }
                continue

            if not (typekey and pathkey):
                logger.warning("Not enough info for item: {0}".format(item))
                yield item
                continue
            # custom types mappings
            handlers = [
                x
                for x in subscribers(
                    (self.context, self.context.REQUEST), IPortalTypeMapping
                )
            ]
            for handler in sorted(handlers, key=lambda h: h.order):
                item = handler(item=item, typekey=typekey)
            if item.get("skipped", False):
                if item.get("_uid") in self.items_in:
                    self.items_in[item.get("_uid")]["reason"] = item.get(
                        "skipped_message", ""
                    )
                else:
                    self.items_in[item.get("_uid")] = {
                        "id": item.get("_id"),
                        "portal_type": item[typekey],
                        "title": item.get("title"),
                        "path": item.get("_path"),
                    }
                continue

            yield item

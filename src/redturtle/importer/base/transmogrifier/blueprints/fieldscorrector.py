# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import Matcher
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class FieldsCorrector(object):
    """ This corrects the differences (mainly in naming) of the incoming fields
        with the expected ones.
    """

    def __init__(self, transmogrifier, name, options, previous):
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

        if "properties-key" in options:
            propertieskeys = options["properties-key"].splitlines()
        else:
            propertieskeys = defaultKeys(
                options["blueprint"], name, "properties"
            )
        self.propertieskey = Matcher(*propertieskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]

            if not pathkey:
                # not enough info
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip("/"), None
            )

            if obj is None:
                # path doesn't exist
                yield item
                continue

            # Event specific fields
            if item.get("startDate", False):
                item["start"] = item.get("startDate")
            if item.get("endDate", False):
                item["end"] = item.get("endDate")

            # Dublin core
            if item.get("expirationDate", False):
                item["expires"] = item.get("expirationDate")
            if item.get("effectiveDate", False):
                item["effective"] = item.get("effectiveDate")

            yield item

# -*- coding: utf-8 -*-
from __future__ import print_function
from AccessControl.interfaces import IRoleManager
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import Matcher
from redturtle.importer.base import logger
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class LocalRoles(object):
    """ """

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

        if "local-roles-key" in options:
            roleskeys = options["local-roles-key"].splitlines()
        else:
            roleskeys = defaultKeys(options["blueprint"], name, "local_roles")
        self.roleskey = Matcher(*roleskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            roleskey = self.roleskey(*list(item.keys()))[0]

            if (
                not pathkey or not roleskey or roleskey not in item
            ):  # not enough info
                yield item
                continue
            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip("/"), None
            )
            if obj is None:  # path doesn't exist
                yield item
                continue

            if IRoleManager.providedBy(obj):
                for principal, roles in item[roleskey].items():
                    if roles:
                        obj.manage_addLocalRoles(principal, roles)
                        try:
                            obj.reindexObjectSecurity()
                        except Exception:
                            logger.warning(
                                "Failed to reindexObjectSecurity {}".format(
                                    item["_path"]
                                )
                            )
            yield item

# -*- coding: utf-8 -*-
from Acquisition import aq_base
from plone import api
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultMatcher
from redturtle.importer.base.transmogrifier.utils import traverse
from redturtle.importer.base import logger
from zope.interface import provider
from zope.interface import implementer

import posixpath


@implementer(ISection)
@provider(ISectionBlueprint)
class ConstructorSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.ttool = api.portal.get_tool(name="portal_types")

        self.typekey = defaultMatcher(
            options, "type-key", name, "type", ("portal_type", "Type")
        )
        self.pathkey = defaultMatcher(options, "path-key", name, "path")
        self.required = bool(options.get("required"))
        self.overwrite = options.get("overwrite") in ("true", "True", "1", True, 1)

    def __iter__(self):
        for item in self.previous:
            keys = list(item.keys())
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]
            if not (typekey and pathkey):
                logger.warn("Not enough info for item: {0}".format(item))
                yield item
                continue
            type_, path = item[typekey], item[pathkey]

            # in generale se ce questa cosa qua non va bene
            if type_ in ("Plone Site",):
                continue

            fti = self.ttool.getTypeInfo(type_)
            if fti is None:
                raise Exception("Missing {0} content type".format(type_))

            container, id = posixpath.split(path.strip("/"))
            context = traverse(self.context, container, None)
            if context is None:
                error = "Container {0} does not exist for item {1}".format(
                    container, path
                )
                if self.required:
                    raise KeyError(error)
                logger.warn(error)
                yield item
                continue

            if id.startswith("++"):
                continue

            if getattr(aq_base(context), id, None) is not None:  # item exists
                old = context[id]
                if old.portal_type == "LRF":
                    # it's a Language root folder: don't touch it
                    continue
                if self.overwrite:
                    logger.info("[overwrite] remove object %s", old.absolute_url())
                    del context[id]

                else:
                    yield item
                    continue

            try:
                obj = fti._constructInstance(context, id)
            except (AttributeError, ValueError):
                logger.exception("item:%s id:%s", item, id)
                yield item

            # For CMF <= 2.1 (aka Plone 3)
            if getattr(fti, "_finishConstruction", None):
                obj = fti._finishConstruction(obj)

            if obj.getId() != id:
                item[pathkey] = posixpath.join(container, obj.getId())

            yield item

# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultMatcher
from redturtle.importer.base.transmogrifier.utils import traverse
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware as CatalogAware
from zope.interface import provider, implementer

import logging


logger = logging.getLogger(__name__)


@provider(ISectionBlueprint)
@implementer(ISection)
class ReindexObjectSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.portal_catalog = transmogrifier.context.portal_catalog
        self.pathkey = defaultMatcher(options, "path-key", name, "path")
        self.verbose = options.get("verbose", "0").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self.counter = 0
        self.indexes = [
            it for it in options.get("indexes", "").splitlines() if it
        ]  # noqa

    def __iter__(self):

        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            if not pathkey:  # not enough info
                yield item
                continue
            path = item[pathkey]

            ob = traverse(self.context, str(path).lstrip("/"), None)
            if ob is None:
                yield item
                continue  # object not found

            if not isinstance(ob, CatalogAware):
                yield item
                continue  # can't notify portal_catalog

            if self.verbose:  # add a log to display reindexation progess
                self.counter += 1
                logger.info("Reindex object %s (%s)", path, self.counter)

            # update catalog
            if self.indexes:
                self.portal_catalog.reindexObject(ob, idxs=self.indexes)
            else:
                self.portal_catalog.reindexObject(ob)

            yield item

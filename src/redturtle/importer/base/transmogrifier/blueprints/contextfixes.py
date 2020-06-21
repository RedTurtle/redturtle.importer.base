# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.interfaces import IMigrationContextSteps
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class ContextFixes(object):
    """
    Do specific-context steps
    """

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

    def __iter__(self):
        for item in self.previous:
            obj = self.context.unrestrictedTraverse(
                str(item["_path"]).lstrip("/"), None
            )
            # path doesn't exist
            if obj is None:
                yield item
                continue
            try:
                provider = IMigrationContextSteps(obj)
                provider.doSteps(item)
            except TypeError:
                # adapter not provided
                yield item
                continue
            yield item

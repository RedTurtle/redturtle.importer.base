# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from zope.annotation.interfaces import IAnnotations
from zope.interface import provider
from zope.interface import implementer

import pkg_resources


try:
    pkg_resources.get_distribution("cioppino.twothumbs")
except pkg_resources.DistributionNotFound:
    HAS_RATINGS = False
else:
    from cioppino.twothumbs import rate

    HAS_RATINGS = True


@implementer(ISection)
@provider(ISectionBlueprint)
class CioppinoTwoThumbsRatings(object):

    """ Migrate ratings from cioppino.twothumbs
    """

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

    def __iter__(self):
        for item in self.previous:
            if item.get("_ratings", False):
                obj = self.context.unrestrictedTraverse(
                    str(item["_path"]).lstrip("/"), None
                )
                if obj is None:
                    # path doesn't exist
                    yield item
                    continue
                yays = "cioppino.twothumbs.yays"
                nays = "cioppino.twothumbs.nays"
                rate.setupAnnotations(obj)
                annotations = IAnnotations(obj)
                annotations[yays] = item["_ratings"]["ups"]
                annotations[nays] = item["_ratings"]["downs"]

            yield item

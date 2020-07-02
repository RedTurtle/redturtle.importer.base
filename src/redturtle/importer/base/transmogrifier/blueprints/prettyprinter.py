# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from zope.interface import provider
from zope.interface import implementer

import pprint


@implementer(ISection)
@provider(ISectionBlueprint)
class PrettyPrinter(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.pprint = pprint.PrettyPrinter().pprint

    def __iter__(self):
        def undict(source):
            """ Recurse through the structure and convert dictionaries
                into sorted lists
            """
            res = list()
            if type(source) is dict:
                source = sorted(source.items())
            if type(source) in (list, tuple):
                for item in source:
                    res.append(undict(item))
            else:
                res = source
            # convert a tuple into tuple back
            if type(source) is tuple:
                res = tuple(res)
            return res

        for item in self.previous:
            self.pprint(undict(item))
            yield item

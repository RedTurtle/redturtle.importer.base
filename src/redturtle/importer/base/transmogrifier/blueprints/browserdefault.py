# -*- coding: utf-8 -*-
from Products.CMFDynamicViewFTI.interface import ISelectableBrowserDefault
from redturtle.importer.base.interfaces import ISection, ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultMatcher
from redturtle.importer.base.transmogrifier.utils import traverse
from zope.interface import provider, implementer


@provider(ISectionBlueprint)
@implementer(ISection)
class BrowserDefaultSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, "path-key", name, "path")
        self.layoutkey = defaultMatcher(options, "layout-key", name, "layout")
        self.defaultpagekey = defaultMatcher(
            options, "default-page-key", name, "defaultpage"
        )

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            if not pathkey:
                yield item
                continue

            layoutkey = self.layoutkey(*list(item.keys()))[0]
            defaultpagekey = self.defaultpagekey(*list(item.keys()))[0]

            path = item[pathkey]

            obj = traverse(self.context, str(path).lstrip("/"), None)
            if obj is None:
                yield item
                continue

            if not ISelectableBrowserDefault.providedBy(obj):
                yield item
                continue

            if layoutkey:
                layout = item[layoutkey]
                if layout:
                    obj.setLayout(str(layout))

            if defaultpagekey:
                defaultpage = item[defaultpagekey]
                if defaultpage:
                    obj.setDefaultPage(str(defaultpage))

            yield item

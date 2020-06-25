# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import Matcher
from plone.dexterity.interfaces import IDexterityContent
from zope.interface import provider
from zope.interface import implementer

import pkg_resources

try:
    pkg_resources.get_distribution("plone.app.multilingual")
except pkg_resources.DistributionNotFound:
    HAS_PAM = False
else:
    from plone.app.multilingual.interfaces import ITranslationManager

    HAS_PAM = True


@implementer(ISection)
@provider(ISectionBlueprint)
class PAMLinker(object):
    """ Links provided translations using plone.app.multilingual. It assumes
        that the object to be linked objects are already in place, so this
        section is intended to be run on second pass migration phase.
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

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]

            if HAS_PAM:
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

                if item.get("_translations", False):
                    lang_info = []
                    for lang in item["_translations"]:
                        target_obj = self.context.unrestrictedTraverse(
                            str(
                                "{0}{1}".format(lang, item["_translations"][lang])
                            ).lstrip("/"),
                            None,
                        )  # noqa
                        if target_obj and (
                            IDexterityContent.providedBy(target_obj)
                        ):  # noqa
                            lang_info.append((target_obj, lang))
                    try:
                        self.link_translations(lang_info)
                    except IndexError:
                        continue

            yield item

    def link_translations(self, items):
        """
            Links the translations with the declared items with the form:
            [(obj1, lang1), (obj2, lang2), ...] assuming that the first element
            is the 'canonical' (in PAM there is no such thing).
        """
        # Grab the first item object and get its canonical handler
        canonical = ITranslationManager(items[0][0])

        for obj, language in items:
            if not canonical.has_translation(language):
                canonical.register_translation(language, obj)

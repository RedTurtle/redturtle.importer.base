# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import Matcher
from DateTime import DateTime
from dateutil.parser import parse
from plone.dexterity.interfaces import IDexterityContent
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class LeftOvers(object):
    """ """

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.transmogrifier.default_pages = []
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
            propertieskeys = defaultKeys(options["blueprint"], name, "properties")
        self.propertieskey = Matcher(*propertieskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            # propertieskey = self.propertieskey(*list(item.keys()))[0]

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

            # Exclude from nav
            if item.get("excludeFromNav", False):
                obj.exclude_from_nav = item.get("excludeFromNav")

            # Open in new window
            if item.get("obrirfinestra", False):
                obj.open_link_in_new_window = item.get("obrirfinestra")
            # Layout and DefaultPage from unicode to str
            if item.get("_layout", False):
                item["_layout"] = str(item["_layout"])
                obj.setLayout(item["_layout"])
            if item.get("_defaultpage", False):
                item["_defaultpage"] = str(item["_defaultpage"])
                # XXX: setDefaultPage si aspetta che la default esista
                # nel folder, se la cartella viene creata prima della
                # default questo non e' possibile, copiata la funzione
                # senza questo controllo da qui:
                # parts/omelette/Products/CMFDynamicViewFTI/browserdefault.py
                # obj.setDefaultPage(item['_defaultpage'])
                # try:
                #     obj.manage_addProperty(
                #         "default_page", item["_defaultpage"], "string"
                #     )
                # except Exception:
                #     pass

                # obj.reindexObject(["is_default_page"])

                # Salviamo le pagine di default all'interno del trasmogrifier
                # alla fine della migrazione le andiamo a recuperare e le
                # assegnamo
                defaultPage = {}
                defaultPage["obj"] = obj.UID()
                defaultPage["default_page"] = item["_defaultpage"]
                self.transmogrifier.default_pages.append(defaultPage)

            # Local roles inherit
            if item.get("_local_roles_block", False):
                if item["_local_roles_block"]:
                    obj.__ac_local_roles_block__ = True

            # Put creation and modification time on its place
            if item.get("creation_date", False):
                if IDexterityContent.providedBy(item):
                    obj.creation_date = parse(item.get("creation_date"))
                else:
                    obj.creation_date = DateTime(item.get("creation_date"))

            if item.get("modification_date", False):
                if IDexterityContent.providedBy(obj):
                    obj.modification_date = parse(item.get("modification_date"))
                else:
                    obj.creation_date = DateTime(item.get("modification_date"))

            # Set subjects
            if item.get("subject", False):
                obj.setSubject(item["subject"])

            yield item

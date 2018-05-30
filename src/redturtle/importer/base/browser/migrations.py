# -*- coding: utf-8 -*-
from collective.transmogrifier.transmogrifier import Transmogrifier
from plone import api
from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import iterSchemata
from plone.protect.interfaces import IDisableCSRFProtection
from Products.Five.browser import BrowserView
from redturtle.importer.base import logger
from transmogrify.dexterity.interfaces import IDeserializer
from zope.event import notify
from zope.interface import alsoProvides
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldsInOrder


class RedTurtlePlone5MigrationMain(BrowserView):

    def __call__(self):
        alsoProvides(self.request, IDisableCSRFProtection)

        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('redturtle.plone5.main')

        # nel transmogrifier c'e' una lista di tuple:
        # (path, fieldname, value) per le quali vanno rifatte le relations
        for (path, fieldname, value) in getattr(transmogrifier, "fixrelations", []):  # noqa
            logger.info('fix %s %s %s', path, fieldname, value)
            obj = self.context.unrestrictedTraverse(path)
            for schemata in iterSchemata(obj):
                for name, field in getFieldsInOrder(schemata):
                    if name == fieldname:
                        if isinstance(value, basestring):
                            value = uuidToObject(value)
                        else:
                            value = [uuidToObject(uuid) for uuid in value]
                        deserializer = IDeserializer(field)
                        value = deserializer(
                            value, [], {}, True, logger=logger)
                        # self.disable_constraints,
                        # logger=self.log,
                        field.set(field.interface(obj), value)
                        notify(ObjectModifiedEvent(obj))

        return 'DONE.'

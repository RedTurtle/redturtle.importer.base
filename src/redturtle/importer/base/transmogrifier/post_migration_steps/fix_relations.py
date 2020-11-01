# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import IPostMigrationStep
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from plone import api
from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import iterSchemata
from redturtle.importer.base.interfaces import IDeserializer
from zope.component import queryMultiAdapter
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldsInOrder

import logging
import six


logger = logging.getLogger(__name__)


@adapter(Interface, Interface)
@implementer(IPostMigrationStep)
class FixRelations(object):
    order = 1

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, transmogrifier):
        """
        """
        # nel transmogrifier c'e' una lista di tuple:
        # (path, fieldname, value) per le quali vanno rifatte le relations
        logger.info("## Fix Relations ##")
        relations = getattr(transmogrifier, "fixrelations", [])
        for (path, fieldname, value) in relations:
            if not value:
                continue
            obj = api.content.get(path)
            if not obj:
                logger.warning(
                    "[FIX RELATIONS] - Unable to find {path}. No relations fixed.".format(  # noqa
                        path=path
                    )
                )
                continue
            logger.info("fix {0} {1} {2}".format(path, fieldname, value))
            for schemata in iterSchemata(obj):
                for name, field in getFieldsInOrder(schemata):
                    if name == fieldname:
                        if isinstance(value, six.string_types):
                            value = uuidToObject(value)
                        else:
                            value = [uuidToObject(uuid) for uuid in value]
                        deserializer = queryMultiAdapter(
                            (field, obj), IDeserializer
                        )
                        value = deserializer(
                            value, [], {}, True, logger=logger
                        )
                        field.set(field.interface(obj), value)
                        notify(ObjectModifiedEvent(obj))

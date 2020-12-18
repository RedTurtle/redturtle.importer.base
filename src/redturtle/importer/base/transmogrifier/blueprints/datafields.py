# -*- coding: utf-8 -*-
from __future__ import print_function
from plone import api
from plone.dexterity.utils import iterSchemata
from redturtle.importer.base import logger
from zope.component import queryMultiAdapter
from redturtle.importer.base.interfaces import IDeserializer
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import ERROREDKEY
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer
from zope.interface import provider
from zope.schema import getFieldsInOrder


@implementer(ISection)
@provider(ISectionBlueprint)
class DataFields(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.datafield_prefix = options.get("datafield-prefix", "_datafield_")
        self.root_path_length = len(self.context.getPhysicalPath())
        self.errored = IAnnotations(api.portal.get().REQUEST).setdefault(
            ERROREDKEY, []
        )

    def __iter__(self):
        for item in self.previous:
            # not enough info
            if "_path" not in item:
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item["_path"].lstrip("/")), None
            )

            # path doesn't exist
            if obj is None:
                yield item
                continue

            # do nothing if we got a wrong object through acquisition
            path = item["_path"]
            if path.startswith("/"):
                path = path[1:]
            if (
                "/".join(obj.getPhysicalPath()[self.root_path_length :])
                != path
            ):
                yield item
                continue

            for key in item.keys():

                if not key.startswith(self.datafield_prefix):
                    continue

                fieldname = key[len(self.datafield_prefix) :]

                field = None
                for schemata in iterSchemata(obj):
                    for name, s_field in getFieldsInOrder(schemata):
                        if name == fieldname:
                            field = s_field
                            try:
                                deserializer = queryMultiAdapter(
                                    (field, obj), IDeserializer
                                )
                                value = deserializer(item[key], None, item)
                            except Exception as e:
                                logger.exception(e)
                                self.errored.append(
                                    {
                                        "path": path,
                                        "reason": "Deserialization Error",
                                    }
                                )
                                continue
                            field.set(field.interface(obj), value)
                if not field:
                    logger.warning(
                        "Can't find a suitable destination field ".format(
                            fieldname
                        )
                    )

            yield item

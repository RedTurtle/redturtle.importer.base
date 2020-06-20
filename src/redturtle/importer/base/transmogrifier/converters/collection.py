# -*- coding: utf-8 -*-
from six import string_types
from redturtle.importer.base.interfaces import IDeserializer
from redturtle.importer.base.transmogrifier.converters.default import (
    DefaultDeserializer,
)
from zope.component import adapter
from zope.interface import implementer
from zope.schema.interfaces import ICollection


@implementer(IDeserializer)
@adapter(ICollection)
class CollectionDeserializer(object):
    def __init__(self, field):
        self.field = field

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        field = self.field
        if value in (None, ""):
            return []
        if isinstance(value, string_types):
            value = [v for v in (v.strip() for v in value.split(";")) if v]
        if field.value_type is not None:
            deserializer = IDeserializer(self.field.value_type)
        else:
            deserializer = DefaultDeserializer(None)
        value = [
            deserializer(
                v, filestore, item, disable_constraints, logger=logger
            )
            for v in value
        ]
        value = field._type(value)
        try:
            self.field.validate(value)
        except Exception as e:
            if not disable_constraints:
                raise e
            else:
                if logger:
                    logger(
                        "%s is invalid in %s: %s"
                        % (self.field.__name__, item["_path"], e)
                    )
        return value

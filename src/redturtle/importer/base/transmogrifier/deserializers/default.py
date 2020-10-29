# -*- coding: utf-8 -*-
from Products.CMFPlone.utils import safe_unicode
from redturtle.importer.base.interfaces import IDeserializer
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from zope.schema.interfaces import IField
from zope.schema.interfaces import IFromUnicode


@implementer(IDeserializer)
@adapter(IField, Interface)
class DefaultDeserializer(object):
    def __init__(self, field, context):
        self.field = field
        self.context = context

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        field = self.field
        if field is not None:
            try:
                if isinstance(value, str):
                    value = safe_unicode(value)
                if str(type(value)) == "<type 'unicode'>":
                    value = IFromUnicode(field).fromUnicode(value)
                self.field.validate(value)
            except Exception as e:
                if not disable_constraints:
                    raise e
                else:
                    if logger:
                        logger(
                            "%s is invalid in %s: %s"
                            % (
                                self.field.__name__,
                                item["_path"],
                                e.__repr__(),
                            )
                        )
        return value

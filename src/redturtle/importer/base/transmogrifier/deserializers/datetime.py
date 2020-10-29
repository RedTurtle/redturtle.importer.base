# -*- coding: utf-8 -*-
from DateTime import DateTime
from datetime import datetime
from zope.schema.interfaces import IDatetime
from plone.app.event.base import default_timezone
from redturtle.importer.base.interfaces import IDeserializer
from zope.interface import implementer
from zope.interface import Interface
from zope.component import adapter

import dateutil.parser
import six


@implementer(IDeserializer)
@adapter(IDatetime, Interface)
class DatetimeDeserializer(object):
    def __init__(self, field, context):
        self.field = field
        self.context = context

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        if value == "None":
            return None
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, six.string_types):
            # Fix some rare use case
            if "Universal" in value:
                value = value.replace("Universal", "UTC")
            try:
                value = dateutil.parser.isoparse(value)
                # Fix timezone
                tz_default = default_timezone(as_tzinfo=True)
                if value.tzinfo is None:
                    value = tz_default.localize(value)
                value = value.astimezone(tz_default)
            except ValueError:
                value = DateTime(value)
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

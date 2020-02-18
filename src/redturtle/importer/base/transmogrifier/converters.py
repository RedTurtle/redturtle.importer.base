# -*- coding: utf-8 -*-
from DateTime import DateTime
from datetime import datetime
from zope.schema.interfaces import IDatetime
from plone.app.event.base import default_timezone
from transmogrify.dexterity.interfaces import IDeserializer
from transmogrify.dexterity.converters import NamedFileDeserializer
from zope.interface import implementer
from zope.component import adapter

import base64
import dateutil.parser
import requests
import six


@implementer(IDeserializer)
@adapter(IDatetime)
class DatetimeDeserializer(object):
    def __init__(self, field):
        self.field = field

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        if value == 'None':
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


class IFixedDeserializer(IDeserializer):
    pass


@implementer(IFixedDeserializer)
class FixedDeserializer(NamedFileDeserializer):
    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        if isinstance(value, dict):
            filename = value.get("filename", None)
            contenttype = str(value.get("contenttype", ""))
            if not contenttype:
                # like in jsonify
                contenttype = str(value.get("content_type", ""))
            file = value.get("file", None)
            if file is not None:
                data = filestore[file]["data"]
            else:
                if value.get("encoding", None) == "base64":
                    # collective.jsonify encodes base64
                    data = base64.b64decode(value["data"])
                else:
                    data_uri = value.get("data_uri", None)
                    if data_uri is not None:
                        try:
                            request = requests.get(data_uri)
                            request.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            logger(
                                "%s error in HTTP request to  %s"
                                % (e, data_uri)
                            )
                        finally:
                            data = request.content
                    else:
                        data = value["data"]

        elif isinstance(value, str):
            data = value
            filename = item.get("_filename", None)
            contenttype = ""
        else:
            raise ValueError("Unable to convert to named file")
        instance = self.field._type(
            data=data, filename=filename, contentType=contenttype
        )
        try:
            self.field.validate(instance)
        except Exception as e:
            if not disable_constraints:
                raise e
            else:
                if logger:
                    logger(
                        "%s is invalid in %s: %s"
                        % (self.field.__name__, item["_path"], e)
                    )
        return instance

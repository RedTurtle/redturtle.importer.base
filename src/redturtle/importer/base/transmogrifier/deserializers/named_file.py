# -*- coding: utf-8 -*-
from plone.namedfile.interfaces import INamedField
from redturtle.importer.base.interfaces import IDeserializer
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface

import base64
import requests


@implementer(IDeserializer)
@adapter(INamedField, Interface)
class NamedFileDeserializer(object):
    def __init__(self, field, context):
        self.field = field
        self.context = context

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

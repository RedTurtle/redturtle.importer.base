# -*- coding: utf-8 -*-
from plone.app.textfield.interfaces import IRichText
from plone.app.textfield.value import RichTextValue
from Products.CMFPlone.utils import safe_unicode
from redturtle.importer.base.interfaces import IDeserializer
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface


def get_site_encoding():
    # getSiteEncoding was in plone.app.textfield.utils but is not gone. Like
    # ``Products.CMFPlone.browser.ploneview``, it always returned 'utf-8',
    # something we can do ourselves here.
    # TODO: use some sane getSiteEncoding from CMFPlone, once there is one.
    return "utf-8"


@implementer(IDeserializer)
@adapter(IRichText, Interface)
class RichTextDeserializer(object):
    _type = RichTextValue

    def __init__(self, field, context):
        self.field = field
        self.context = context

    def _convert_object(self, obj, encoding):
        """Decode binary strings into unicode objects
        """
        return safe_unicode(obj)

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        if isinstance(value, dict):
            encoding = value.get("encoding", get_site_encoding())
            contenttype = value.get("contenttype", None)
            if contenttype is not None:
                contenttype = str(contenttype)
            file = value.get("file", None)
            if file is not None:
                data = self._convert_object(filestore[file]["data"], encoding)
            else:
                data = self._convert_object(value["data"], encoding)
        else:
            encoding = get_site_encoding()
            data = self._convert_object(value, encoding)
            contenttype = None
        if contenttype is None:
            contenttype = self.field.default_mime_type
        instance = self._type(
            raw=data,
            mimeType=contenttype,
            outputMimeType=self.field.output_mime_type,
            encoding=encoding,
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

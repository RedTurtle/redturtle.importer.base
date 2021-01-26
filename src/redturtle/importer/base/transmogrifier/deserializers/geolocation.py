# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import IDeserializer
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from plone.formwidget.geolocation.geolocation import Geolocation
from plone.formwidget.geolocation.interfaces import IGeolocationField


@implementer(IDeserializer)
@adapter(IGeolocationField, Interface)
class GeolocationDeserializer(object):

    default_value = None

    def __init__(self, field, context):
        self.field = field
        self.context = context

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        field = self.field
        if field is None:
            return None

        if not value:
            return self.default_value

        return Geolocation(
            latitude=value["latitude"], longitude=value["longitude"]
        )

# -*- coding: utf-8 -*-
from zope.interface import Interface


class IMigrationContextSteps(Interface):
    """
    Marker interface for specific context steps
    """


class IDeserializer(Interface):
    def __call__(value, filestore, item):
        """Convert to a field value
        """

# -*- coding: utf-8 -*-
from plone.formwidget.masterselect import IMasterSelectField
from transmogrify.dexterity.converters import DefaultDeserializer
from transmogrify.dexterity.interfaces import IDeserializer
from zope.component import adapter
from zope.interface import implementer


@implementer(IDeserializer)
@adapter(IMasterSelectField)
class MasterSelectDeserializer(DefaultDeserializer):
    pass

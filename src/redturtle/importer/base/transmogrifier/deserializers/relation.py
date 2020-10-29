# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import IDeserializer
from zope.component import adapter
from zope.component import queryUtility
from zope.interface import implementer
from zope.interface import Interface

import pkg_resources


try:
    pkg_resources.get_distribution("plone.app.intid")
except pkg_resources.DistributionNotFound:
    INTID_AVAILABLE = False
else:
    INTID_AVAILABLE = True
    from zope.intid.interfaces import IIntIds

try:
    pkg_resources.get_distribution("z3c.relationfield")
except:
    RELATIONFIELD_AVAILABLE = False
else:
    RELATIONFIELD_AVAILABLE = True
    from z3c.relationfield.interfaces import IRelation
    from z3c.relationfield.interfaces import IRelationList
    from z3c.relationfield.relation import RelationValue


if INTID_AVAILABLE and RELATIONFIELD_AVAILABLE:

    @implementer(IDeserializer)
    @adapter(IRelation, Interface)
    class RelationDeserializer(object):

        default_value = None

        def __init__(self, field, context):
            self.field = field
            self.context = context

        def __call__(
            self,
            value,
            filestore,
            item,
            disable_constraints=False,
            logger=None,
        ):
            field = self.field
            if field is None:
                return None

            if not value:
                return self.default_value

            self.intids = queryUtility(IIntIds)
            if self.intids is None:
                return value

            return self.deserialize(value)

        def deserialize(self, value):
            int_id = self.intids.queryId(value)
            if int_id is None:
                return value

            return RelationValue(int_id)

    @implementer(IDeserializer)
    @adapter(IRelationList, Interface)
    class RelationListDeserializer(RelationDeserializer):

        default_value = []

        def deserialize(self, value):
            result = []
            for obj in value:
                result.append(
                    super(RelationListDeserializer, self).deserialize(obj)
                )
            return result

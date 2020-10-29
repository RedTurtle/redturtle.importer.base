# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import IDeserializer
from redturtle.importer.base.transmogrifier.deserializers.default import (
    DefaultDeserializer,
)
from zope.component import adapter
from zope.component import queryMultiAdapter
from zope.dottedname.resolve import resolve
from zope.interface import implementer
from zope.interface import Interface
from zope.schema.interfaces import IObject


@implementer(IDeserializer)
@adapter(IObject, Interface)
class ObjectDeserializer(object):
    def __init__(self, field, context):
        self.field = field
        self.context = context

    def __call__(
        self, value, filestore, item, disable_constraints=False, logger=None
    ):
        if not isinstance(value, dict):
            raise ValueError("Need a dict to convert")
        if not value.get("_class", None):
            try:
                # NB: datagridfield creates it's own Serializer, but falls
                # back to this Deserializer. _class will be missing in this
                # case.
                from collective.z3cform.datagridfield.row import DictRow

                if isinstance(self.field, DictRow):
                    # NB: Should be recursing into the dict and deserializing,
                    # but that can be fixed within datagridfield
                    return DefaultDeserializer(self.field)(
                        value,
                        filestore,
                        item,
                        disable_constraints=disable_constraints,
                        logger=logger,
                    )
            except ImportError:
                pass
            raise ValueError("_class is missing")

        # Import _class and create instance, if it implments what we need
        klass = resolve(value["_class"])
        if not self.field.schema.implementedBy(klass):
            raise ValueError(
                "%s does not implemement %s"
                % (value["_class"], self.field.schema)
            )
        instance = klass()

        # Add each key from value to instance
        for (k, v) in value.items():
            if k == "_class":
                continue
            if not hasattr(instance, k):
                raise ValueError("%s is not an object attribute" % k)
            if v is None:
                setattr(instance, k, None)
                continue

            if k in self.field.schema:
                deserializer = queryMultiAdapter(
                    (self.field.schema[k], self.context), IDeserializer
                )
            else:
                deserializer = DefaultDeserializer(None)
            setattr(
                instance,
                k,
                deserializer(
                    v,
                    filestore,
                    item,
                    disable_constraints=disable_constraints,
                    logger=logger,
                ),
            )

        if not disable_constraints:
            self.field.validate(instance)
        return instance

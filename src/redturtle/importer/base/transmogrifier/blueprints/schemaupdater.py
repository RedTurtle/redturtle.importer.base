# -*- coding: utf-8 -*-
from __future__ import print_function
from plone import api
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.uuid.interfaces import IMutableUUID
from redturtle.importer.base.interfaces import IDeserializer
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultMatcher
from redturtle.importer.base.transmogrifier.utils import Expression
from redturtle.importer.base.transmogrifier.utils import ERROREDKEY
from z3c.form import interfaces
from z3c.relationfield.interfaces import IRelationChoice
from z3c.relationfield.interfaces import IRelationList
from zope.annotation.interfaces import IAnnotations
from zope.component import getMultiAdapter
from zope.component import queryMultiAdapter
from zope.event import notify
from zope.interface import implementer
from zope.interface import provider
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldsInOrder

import logging


_marker = object()


@implementer(ISection)
@provider(ISectionBlueprint)
class DexterityUpdateSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.transmogrifier.fixrelations = []
        self.previous = previous
        self.context = transmogrifier.context
        self.name = name
        self.pathkey = defaultMatcher(options, "path-key", name, "path")
        self.fileskey = options.get("files-key", "_files").strip()
        self.disable_constraints = Expression(
            options.get("disable-constraints", "python: False"),
            transmogrifier,
            name,
            options,
        )

        # create logger
        if options.get("logger"):
            self.logger = logging.getLogger(options["logger"])
            self.loglevel = getattr(logging, options["loglevel"], None)
            if self.loglevel is None:
                # Assume it's an integer:
                self.loglevel = int(options["loglevel"])
            self.logger.setLevel(self.loglevel)
            self.log = lambda s: self.logger.log(self.loglevel, s)
        else:
            self.log = None
        self.errored = IAnnotations(api.portal.get().REQUEST).setdefault(ERROREDKEY, [])

    def __iter__(self):  #  noqa
        # need to be refactored
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            # not enough info
            if not pathkey:
                yield item
                continue

            path = item[pathkey]
            # Skip the Plone site object itself
            if not path:
                yield item
                continue

            obj = self.context.unrestrictedTraverse(path.lstrip("/"), None)

            # path doesn't exist
            if obj is None:
                yield item
                continue

            if IDexterityContent.providedBy(obj):
                uuid = item.get("plone.uuid")
                if uuid is not None:
                    try:
                        IMutableUUID(obj).set(str(uuid))
                    except Exception:
                        self.errored.append(item["_original_path"])

                files = item.setdefault(self.fileskey, {})

                # For all fields in the schema, update in roughly the same way
                # z3c.form.widget.py would
                for schemata in iterSchemata(obj):
                    for name, field in getFieldsInOrder(schemata):

                        if name == "id":
                            continue
                        if field.readonly:
                            continue
                        # setting value from the blueprint cue
                        value = item.get(name, _marker)
                        if value is not _marker:
                            if IRelationList.providedBy(
                                field
                            ) or IRelationChoice.providedBy(
                                field
                            ):  # noqa
                                self.transmogrifier.fixrelations.append(
                                    ("/".join(obj.getPhysicalPath()), name, value)
                                )  # noqa
                            # Value was given in pipeline, so set it
                            deserializer = queryMultiAdapter(
                                (field, obj), IDeserializer
                            )
                            try:
                                if value:
                                    value = deserializer(
                                        value,
                                        files,
                                        item,
                                        self.disable_constraints,
                                        logger=self.log,
                                    )
                                field.set(field.interface(obj), value)
                                continue
                            except Exception:
                                continue

                        # Get the widget's current value, if it has one then
                        # leave it alone
                        value = getMultiAdapter(
                            (obj, field), interfaces.IDataManager
                        ).query()
                        if not (
                            value is field.missing_value or value is interfaces.NO_VALUE
                        ):
                            continue

                        # Finally, set a default value if nothing is set so far
                        default = queryMultiAdapter(
                            (
                                obj,
                                obj.REQUEST,  # request
                                None,  # form
                                field,
                                None,  # Widget
                            ),
                            interfaces.IValue,
                            name="default",
                        )

                        if schemata.__name__ == "IAllowDiscussion":
                            default = item.get("allow_discusion", None)
                            field.set(field.interface(obj), default)
                            continue

                        if default is not None:
                            default = default.get()
                        if default is None:
                            default = getattr(field, "default", None)
                        if default is None:
                            try:
                                default = field.missing_value
                            except AttributeError:
                                pass
                        field.set(field.interface(obj), default)
                notify(ObjectModifiedEvent(obj))
            yield item

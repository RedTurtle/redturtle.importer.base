# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.uuid.interfaces import IMutableUUID
from ploneorg.migration.browser.schemaupdater import DexterityUpdateSection as BaseDexterityUpdateSection  # noqa
from transmogrify.dexterity.interfaces import IDeserializer
from z3c.form import interfaces
from z3c.relationfield.interfaces import IRelationChoice
from z3c.relationfield.interfaces import IRelationList
from zope.component import getMultiAdapter
from zope.component import queryMultiAdapter
from zope.event import notify
from zope.interface import classProvides
from zope.interface import implementer
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldsInOrder


_marker = object()


@implementer(ISection)
class DexterityUpdateSection(BaseDexterityUpdateSection):
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.transmogrifier.fixrelations = []
        super(DexterityUpdateSection, self).__init__(
            transmogrifier, name, options, previous)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            # not enough info
            if not pathkey:
                yield item
                continue

            path = item[pathkey]
            # Skip the Plone site object itself
            if not path:
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                path.encode().lstrip('/'), None)

            # path doesn't exist
            if obj is None:
                yield item
                continue

            if IDexterityContent.providedBy(obj):
                uuid = item.get('plone.uuid')
                if uuid is not None:
                    try:
                        IMutableUUID(obj).set(str(uuid))
                    except Exception:
                        self.errored.append(item['_original_path'])

                files = item.setdefault(self.fileskey, {})

                # For all fields in the schema, update in roughly the same way
                # z3c.form.widget.py would
                # import pdb; pdb.set_trace()
                for schemata in iterSchemata(obj):
                    for name, field in getFieldsInOrder(schemata):
                        if name == 'id':
                            continue
                        if field.readonly:
                            continue

                        # setting value from the blueprint cue
                        value = item.get(name, _marker)
                        if value is not _marker:
                            if IRelationList.providedBy(field) or IRelationChoice.providedBy(field):  # noqa
                                self.transmogrifier.fixrelations.append(
                                    ('/'.join(obj.getPhysicalPath()), name, value))  # noqa
                            # Value was given in pipeline, so set it
                            deserializer = IDeserializer(field)
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
                            (obj, field),
                            interfaces.IDataManager).query()
                        if not(value is field.missing_value
                               or value is interfaces.NO_VALUE):
                            continue

                        # Finally, set a default value if nothing is set so far
                        default = queryMultiAdapter((
                            obj,
                            obj.REQUEST,  # request
                            None,  # form
                            field,
                            None,  # Widget
                        ), interfaces.IValue, name='default')

                        if schemata.__name__ == 'IAllowDiscussion':
                            default = item.get('allow_discusion', None)
                            field.set(field.interface(obj), default)
                            continue

                        if default is not None:
                            default = default.get()
                        if default is None:
                            default = getattr(field, 'default', None)
                        if default is None:
                            try:
                                default = field.missing_value
                            except AttributeError:
                                pass
                        field.set(field.interface(obj), default)
                try:
                    notify(ObjectModifiedEvent(obj))
                except Exception:
                    print 'Error probably in linkintegrity transform'
            yield item

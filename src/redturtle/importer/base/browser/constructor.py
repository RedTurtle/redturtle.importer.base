# -*- coding: utf-8 -*-
from Acquisition import aq_base
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.sections.constructor import ConstructorSection \
    as BaseConstructorSection
from collective.transmogrifier.utils import traverse
from redturtle.importer.base import logger
from zope.interface import classProvides
from zope.interface import implementer

import posixpath


@implementer(ISection)
class ConstructorSection(BaseConstructorSection):
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        super(ConstructorSection, self).__init__(
            transmogrifier, name, options, previous)
        self.overwrite = (
            options.get('overwrite') in ('true', 'True', '1', True, 1)
        )

    def __iter__(self):
        for item in self.previous:
            keys = item.keys()
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]

            if not (typekey and pathkey):
                logger.warn('Not enough info for item: {0}'.format(item))
                yield item
                continue
            type_, path = item[typekey], item[pathkey]

            fti = self.ttool.getTypeInfo(type_)
            # if fti is None:
            #     logger.warn('Not an existing type: %s' % type_)
            #     yield item
            #     continue
            if fti is None:
                logger.warn(
                    'Not an existing type, converted into Folder: {0}'.format(
                        type_
                    )
                )
                fti = self.ttool.getTypeInfo('Folder')

            path = path.encode('ASCII')
            container, id = posixpath.split(path.strip('/'))
            context = traverse(self.context, container, None)
            if context is None:
                error = 'Container {0} does not exist for item {1}'.format(
                    container, path
                )
                if self.required:
                    raise KeyError(error)
                logger.warn(error)
                yield item
                continue

            if id.startswith('++'):
                continue

            if getattr(aq_base(context), id, None) is not None:  # item exists
                old = context[id]
                if self.overwrite:
                    logger.info(
                        '[overwrite] remove object %s', old.absolute_url()
                    )
                    del(context[id])

                # if old.portal_type != type_:
                    # REMOVE WRONG object
                    # logger.info("[overwrite] remove object %s", old.absolute_url())
                    # api.content.delete(obj=old)  # questo modo (in teoria migliore) lancia eccezioni sull'integrity, permessi, ...
                    # del(context[id])

                else:
                    yield item
                    continue

            try:
                obj = fti._constructInstance(context, id)
            except (AttributeError, ValueError):
                # Module rer.plone5.migration.browser.import.constructor, line 54, in __iter__
                # Module Products.CMFCore.TypesTool, line 569, in _constructInstance
                # AttributeError: _setObject
                logger.exception('item:%s id:%s', item, id)
                # error = 'Problemi for item %s' % (path)
                # raise ValueError(error)
                yield item

            # For CMF <= 2.1 (aka Plone 3)
            if hasattr(fti, '_finishConstruction'):
                obj = fti._finishConstruction(obj)

            if obj.getId() != id:
                item[pathkey] = posixpath.join(container, obj.getId())

            yield item

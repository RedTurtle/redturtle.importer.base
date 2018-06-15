# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultKeys
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import Matcher
from redturtle.importer.base import logger
from zope.interface import classProvides
from zope.interface import implements


class ContentsMappingSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        self.typekey = defaultMatcher(options, 'type-key', name, 'type',
                                      ('portal_type', 'Type'))

    def collection_mapping(self, item):
        mapping = {
            'portal_type': 'plone.app.querystring.operation.selection.any',
            'review_state': 'plone.app.querystring.operation.selection.any'
        }

        query = item['query']
        for criteria in query:
            # Fix query string opertaion
            proper_operation = mapping.get(criteria.get('i'))
            if proper_operation:
                logger.info('Changed collection criteria for %s from %s to %s for item: %s' % (
                    criteria.get('i'), criteria.get('o'), proper_operation, item['_path']))
                criteria.update({'o': proper_operation})
            # Fix path format if a uid is specified
            if 'path' in criteria.values():
                path_value = criteria.get('v')
                if not '::' in path_value:
                    continue
                uid, number = path_value.split("::")
                if uid:
                    fixed_uid = '%s::-%s' % (uid, number)
                    criteria.update({'v': fixed_uid})

    def __iter__(self):
        for item in self.previous:
            keys = item.keys()
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]

            if not (typekey and pathkey):
                logger.warn('Not enough info for item: %s' % item)
                yield item
                continue

            if item[typekey] == 'Topic':
                item[typekey] = 'Collection'
                yield item

            elif item[typekey] == 'Collection':
                item[typekey] = 'Collection'
                self.collection_mapping(item)
                yield item

            elif item[typekey] == 'Link':
                item['internal_link'] = item['internalLink']
                item['remoteUrl'] = item['externalLink']

                del item['internalLink']
                del item['externalLink']
                yield item

            else:
                yield item

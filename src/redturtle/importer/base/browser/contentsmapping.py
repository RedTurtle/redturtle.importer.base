# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultKeys
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import Matcher
from redturtle.importer.base import logger
from redturtle.importer.base.utils import get_additional_config
from zope.interface import classProvides
from zope.interface import implements

import ast


class ContentsMappingSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        # read additional config in cfg file, and apply to default
        additional_config = get_additional_config('contentsmapping')
        self.debug_infos = {}
        options.update(additional_config)

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
        self.exclude_type = ast.literal_eval(options.get('exclude-type', None))

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

            # integrazione check del tipo all'interno di questo ciclo
            skip = False
            if self.exclude_type:
                for type in self.exclude_type:
                    # fathers type
                    if item.get('fathers_type_list', None):
                        for fathers_type in item['fathers_type_list']:
                            if fathers_type == type:
                                skip = True
                                break
                            if skip:
                                break
                    else:
                        logger.warn('Item {0} doesn\'t have father'.format(
                            item['_path'])
                        )
                    # check obj type
                    if item.get('_type', None):
                        if item['_type'] == type:
                            skip = True

            if skip:
                continue

            if not (typekey and pathkey):
                logger.warn('Not enough info for item: %s' % item)
                yield item
                continue

            if item[typekey] == 'Topic':
                item[typekey] = 'Collection'
                yield item
                continue

            elif item[typekey] == 'Collection':
                item[typekey] = 'Collection'
                self.collection_mapping(item)
                yield item
                continue

            elif item[typekey] == 'Link':
                internalLink = item.get('internalLink', None)
                if internalLink:
                    item['internal_link'] = internalLink
                    del item['internalLink']
                    # remoteUrl = item.get('remoteUrl', None)
                    # if remoteUrl:
                    #     del item['remoteUrl']

                externalLink = item.get('externalLink', None)
                if externalLink:
                    item['remoteUrl'] = externalLink
                    del item['externalLink']

                yield item
                continue

            else:
                yield item

# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from datetime import datetime
from plone import api
from ploneorg.migration.browser.catalogsource import CatalogSourceSection
from redturtle.importer.base.utils import get_additional_config
from zope.interface import classProvides
from zope.interface import implementer

import hashlib
import json
import logging
import os


logger = logging.getLogger(__name__)


@implementer(ISection)
class CachedCatalogSourceSection(CatalogSourceSection):
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        # read additional config in cfg file, and apply to default
        additional_config = get_additional_config('catalogsource')
        self.debug_infos = {}
        options.update(additional_config)
        super(CachedCatalogSourceSection, self).__init__(
            transmogrifier, name, options, previous)

        # creo tutte le folder dove salvare i file della migrazione
        self.migration_dir = self.get_option('migration-dir', '/tmp/migration')
        if not os.path.exists(self.migration_dir):
            os.makedirs(self.migration_dir)

        # cartella per la cache degli oggetti
        self.cache_dir = self.get_option(
            'cache-dir', '/tmp/migration/migration_cache')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        self.incremental_migration = (
            options.get(
                'incremental-migration'
            ) in ('true', 'True', '1', True, 1)
        )
        self.ignore_cache = (
            options.get('ignore-cache') in ('true', 'True', '1', True, 1)
        )

    def __iter__(self):
        for item in self.previous:
            yield item

        for path in self.item_paths:
            skip = False
            for skip_path in self.remote_skip_paths:
                if path.startswith(self.remote_root + skip_path):
                    skip = True

            # Skip old talkback items
            if 'talkback' in path:
                skip = True

            if not skip:
                item = self.get_remote_item(path)

                if item:
                    item['_path'] = item['_path'][self.site_path_length:]
                    item['_auth_info'] = (
                        self.remote_username, self.remote_password)
                    item['_site_path_length'] = self.site_path_length

                    # Enable logging
                    self.storage.append(item['_path'])

                    # ptype = item.get('_type', False)
                    yield item
        self.save_debug_in_file()

    def save_debug_in_file(self):
        file_name = self.get_option(
            'file-name-in', 'migration_content_in.json')
        file_path = '{0}/{1}'.format(self.migration_dir, file_name)
        with open(file_path, 'w') as fp:
            json.dump(self.debug_infos, fp)

    def slugify(self, path):
        # TODO verificare che non ci siano collisioni
        return hashlib.sha224(path).hexdigest()
        # return base64.urlsafe_b64encode(path)

    def get_local_obj(self, path):
        path = path.replace(self.remote_root, '')
        obj = api.content.get(path=path)
        if not obj:
            logger.info('Item {0} not present locally.'.format(path))
            return None
        return obj

    # TODO: se dal catalogo ci fosse anche lo uid e la data di ultima modifica
    # la cache potrebbe essere ancora più precisa e sarebbe anche possibile
    # una migrazione incrementale, al momento si considera sempre fresh la
    # copia in cache, se c'è.
    def get_remote_item(self, path):
        cachefile = os.path.sep.join(
            [self.cache_dir, self.slugify(path) + '.json']
        )
        item = super(CachedCatalogSourceSection, self).get_remote_item(path)
        if not item:
            logger.info(
                'Export not available, skipping migration for item {0}'.format(
                    path
                )
            )
            return {}

        # incremental migration
        if self.incremental_migration and 'relatedItems' not in item.keys():
            local_obj = self.get_local_obj(path)
            if local_obj:
                local_object_modification_date = getattr(
                    local_obj,
                    'modification_date',
                    ''
                ).asdatetime().replace(second=0, microsecond=0, tzinfo=None)
                remote_object_modification_date = datetime.strptime(
                    item.get('modification_date'),
                    '%Y-%m-%d %H:%M'
                )
                if local_object_modification_date \
                        >= remote_object_modification_date:
                    logger.info(
                        'Preserving destination content, Skipped migration ' +
                        'for item {0}'.format(path)
                    )
                    return {}
                logger.info(
                    'Content {0} modified after {1}. Importing...'.format(
                        path,
                        local_object_modification_date.isoformat()
                    )
                )

        # check element in cache
        if not self.ignore_cache and os.path.exists(cachefile) \
                and 'relatedItems' not in item.keys():
            json_data = json.load(open(cachefile, 'rb'))
            item_mod_date = datetime.strptime(
                item.get('modification_date'),
                '%Y-%m-%d %H:%M'
            )
            item_cache_mod_date = datetime.strptime(
                json_data.get('modification_date'),
                '%Y-%m-%d %H:%M'
            )
            if item_mod_date <= item_cache_mod_date:
                logger.info('HIT path: {0}'.format(path))
                return json_data
            logger.info('MISS path: {0}'.format(path))

        if item:
            json.dump(item, open(cachefile, 'wb'), indent=2)

        self.debug_infos[item.get('_uid')] = {
            'id': item.get('_id'),
            'portal_type': item.get('_type'),
            'title': item.get('title'),
            'path': item.get('_path')
        }

        return item

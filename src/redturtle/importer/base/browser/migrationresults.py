# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from zope.interface import classProvides
from zope.interface import implementer

import json
import os


@implementer(ISection)
class MigrationResults(object):
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.debug_infos = {}
        self.options = options

    def __iter__(self):
        for item in self.previous:
            # metto le info dei file che arrivano in fondo alla pipe
            self.debug_infos[item.get('_uid')] = {
                'id': item.get('_id', None),
                'portal_type': item.get('_type', None),
                'title': item.get('title', None),
                'path': item.get('_path', None)
            }

            yield item
        self.save_debug_out_file()

    def save_debug_out_file(self):
        migration_dir = self.options.get('migration-dir', '/tmp/migration')
        if not os.path.exists(migration_dir):
            os.makedirs(migration_dir)
        file_name = self.options.get(
            'file-name-out', 'migration_content_out.json')
        file_path = '{0}/{1}'.format(migration_dir, file_name)
        with open(file_path, 'w') as fp:
            json.dump(self.debug_infos, fp)

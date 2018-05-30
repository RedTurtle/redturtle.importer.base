# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from zope.interface import classProvides
from zope.interface import implementer

import os


@implementer(ISection)
class MigrationResults(object):
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous

        # folder dove mettere i file
        self.migration_dir = options.get('migration-dir', '/tmp/migration')
        if not os.path.exists(self.migration_dir):
            os.makedirs(self.migration_dir)

        # creo il file dove metto le info sugli elementi che arrivano
        # in fondo alla pipe di migrazione
        file_name = options.get(
            'file-name-out', 'migration_content_out.txt')
        self.file_out = open(self.migration_dir + '/' +
                             file_name, 'w+')

    def __iter__(self):
        for item in self.previous:

            # metto le info dei file che arrivano in fondo alla pipe
            self.file_out.write('UID: {0}, portal_type: {1}, id: {2}\n'.format(
                item['_uid'],
                item['_type'],
                item['id']
            ))

            yield item
        self.file_out.close()

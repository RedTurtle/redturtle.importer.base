# -*- coding: utf-8 -*-
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import ERROREDKEY
from plone import api
from zope.annotation.interfaces import IAnnotations
from zope.interface import provider
from zope.interface import implementer

import json
import os


@implementer(ISection)
@provider(ISectionBlueprint)
class MigrationResults(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.debug_infos = {}
        self.options = options

    def __iter__(self):
        for item in self.previous:
            # metto le info dei file che arrivano in fondo alla pipe
            self.debug_infos[item.get("_uid")] = {
                "id": item.get("_id", None),
                "portal_type": item.get("_type", None),
                "title": item.get("title", None),
                "path": item.get("_path", None),
            }

            yield item
        self.save_debug_out_file()
        self.save_errors_file()

    def get_file_path(self, option_name, default=""):
        migration_dir = self.options.get("migration-dir", "/tmp/migration")
        if not os.path.exists(migration_dir):
            os.makedirs(migration_dir)
        file_name = self.options.get(option_name, default)
        return "{0}/{1}_{2}".format(migration_dir, api.portal.get().getId(), file_name)

    def save_debug_out_file(self):

        file_path = self.get_file_path(
            option_name="file-name-out", default="migration_content_out.json"
        )
        with open(file_path, "w") as fp:
            json.dump(self.debug_infos, fp)

    def save_errors_file(self):
        request = api.portal.get().REQUEST
        annotations = IAnnotations(request).get(ERROREDKEY, None)
        if not annotations:
            return
        file_path = self.get_file_path(option_name="errors_log", default="errors.json")
        with open(file_path, "w") as fp:
            json.dump(annotations, fp)

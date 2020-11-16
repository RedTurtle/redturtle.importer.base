# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from plone import api
from plone.memoize.view import memoize
from Products.Five.browser import BrowserView
from redturtle.importer.base import logger
from redturtle.importer.base.interfaces import IPostMigrationStep
from redturtle.importer.base.transmogrifier.transmogrifier import (
    Transmogrifier,
)
from redturtle.importer.base.transmogrifier.utils import get_additional_config
from redturtle.importer.base.transmogrifier.utils import (
    get_transmogrifier_configuration,
)
from zope.component import subscribers

import json
import os


class RedTurtlePlone5MigrationMain(BrowserView):
    """
    Migration view
    """

    transmogrifier = None
    transmogrifier_conf = "redturtlePlone5Main"

    def __call__(self):
        if not self.request.form.get("confirm", False):
            return self.index()

        return self.do_migrate()

    def do_migrate(self, REQUEST=None):

        authenticator = api.content.get_view(
            context=api.portal.get(),
            request=self.request,
            name=u"authenticator",
        )
        if not authenticator.verify():
            raise Unauthorized

        portal = api.portal.get()
        self.transmogrifier = Transmogrifier(portal)
        # self.cleanup_log_files()
        self.transmogrifier(
            configuration_id=self.transmogrifier_conf,
            **get_additional_config()
        )

        # run scripts after migration
        self.scripts_post_migration()
        logger.info("Migration done.")
        api.portal.show_message(
            message="Migration done. Check logs for a complete report."
            "Scripts after migration running....",
            request=self.request,
        )
        return self.request.response.redirect(
            "{0}/migration-results".format(api.portal.get().absolute_url())
        )

    def scripts_post_migration(self):
        """
        Excecute a series of post migration steps in order
        """
        handlers = [
            x
            for x in subscribers(
                (self.context, self.request), IPostMigrationStep
            )
        ]
        for handler in sorted(handlers, key=lambda h: h.order):
            handler(transmogrifier=self.transmogrifier)

    def get_config(self):
        return get_transmogrifier_configuration()


class MigrationResults(BrowserView):
    """
    read debug files and expose statistics
    """

    @property
    @memoize
    def transmogrifier_conf(self):
        return get_transmogrifier_configuration()

    def get_results(self):

        in_json = self.get_json_data(
            option="file-name-in", section_id="catalogsource"
        )
        out_json = self.get_json_data(
            option="file-name-out", section_id="results"
        )

        results = {
            "in_count": len(list(in_json.keys())),
            "out_count": len(list(out_json.keys())),
            "noreference_links": self.get_noreference_links(),
        }

        if list(out_json.keys()) == list(in_json.keys()):
            results["same_results"] = True
        else:
            results["same_results"] = False
            results["not_migrated"] = self.generate_not_migrated_list(
                in_json=in_json, out_json=out_json
            )

        return results

    def generate_not_migrated_list(self, in_json, out_json):
        diff_keys = set(in_json.keys()) - set(out_json.keys())
        return [in_json[k] for k in diff_keys]

    def get_json_data(self, option, section_id):
        config = self.transmogrifier_conf
        section = config.get(section_id, None)
        file_name = section.get(option, "")
        if not file_name:
            return []
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                return json.loads(fp.read())
        else:
            return {}

    def get_noreference_links(self):
        config = self.transmogrifier_conf
        section = config.get("results", None)
        file_name = section.get("noreference-links")
        file_path = "{dir}/{portal_id}_{file_name}".format(
            dir=section.get("migration-dir"),
            portal_id=api.portal.get().getId(),
            file_name=file_name,
        )
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                return json.loads(fp.read())
        else:
            return []

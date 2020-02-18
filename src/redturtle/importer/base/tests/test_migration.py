# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from App.Common import package_home
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone import api
from plone.protect.authenticator import createToken
from redturtle.importer.base.testing import (
    REDTURTLE_IMPORTER_BASE_DOCKER_FUNCTIONAL_TESTING,  # noqa: E501
)

import os
import unittest


def get_config_file_path(filename):
    return os.path.join(package_home(globals()), 'custom_configs', filename)


class TestBaseMigrationSucceed(unittest.TestCase):
    """
    This test suite works in conjunction with a docker image that runs
    redturtle.exporter.base install profile to pre-populate a site with some
    contents: https://github.com/RedTurtle/redturtle.exporter.base/blob/master/src/redturtle/exporter/base/setuphandlers.py
    """

    layer = REDTURTLE_IMPORTER_BASE_DOCKER_FUNCTIONAL_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.migration_view = api.content.get_view(
            name="data-migration", context=self.portal, request=self.request
        )
        self.request.form['_authenticator'] = createToken()

    def tearDown(self):
        """
        clear site
        """
        api.content.delete(objects=self.portal.listFolderContents())

    def test_base_migration_succeed(self):
        pc = api.portal.get_tool(name='portal_catalog')
        self.assertEqual(len(pc()), 0)

        self.migration_view.do_migrate()

        documents = api.content.find(portal_type="Document")
        folders = api.content.find(portal_type="Folder")
        collections = api.content.find(portal_type="Collection")
        news = api.content.find(portal_type="News Item")
        files = api.content.find(portal_type="File")
        images = api.content.find(portal_type="Image")
        events = api.content.find(portal_type="Event")

        self.assertEqual(len(documents), 4)
        self.assertEqual(len(folders), 6)
        self.assertEqual(len(collections), 3)
        self.assertEqual(len(news), 2)
        self.assertEqual(len(files), 1)
        self.assertEqual(len(images), 1)
        self.assertEqual(len(events), 1)

    def test_do_not_migrate_private_contents(self):
        os.environ["MIGRATION_FILE_PATH"] = get_config_file_path(
            'skip_private.cfg'
        )
        self.migration_view.do_migrate()

        documents = api.content.find(portal_type="Document")
        folders = api.content.find(portal_type="Folder")
        collections = api.content.find(portal_type="Collection")
        news = api.content.find(portal_type="News Item")
        files = api.content.find(portal_type="File")
        images = api.content.find(portal_type="Image")
        events = api.content.find(portal_type="Event")

        self.assertEqual(len(documents), 2)
        self.assertEqual(len(folders), 4)
        self.assertEqual(len(collections), 2)
        self.assertEqual(len(news), 0)
        self.assertEqual(len(events), 0)

        # files and images are inside a private folder
        self.assertEqual(len(files), 0)
        self.assertEqual(len(images), 0)
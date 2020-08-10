# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from App.Common import package_home
from DateTime import DateTime
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone import api
from plone.protect.authenticator import createToken
from redturtle.importer.base.testing import (
    REDTURTLE_IMPORTER_BASE_FUNCTIONAL_TESTING,  # noqa: E501
)

import os
import unittest


def get_config_file_path(filename):
    return os.path.join(package_home(globals()), "custom_configs", filename)


class TestBaseMigrationSucceed(unittest.TestCase):
    """
    This test suite works in conjunction with a docker image that runs
    redturtle.exporter.base install profile to pre-populate a site with some
    contents: https://github.com/RedTurtle/redturtle.exporter.base/blob/master/src/redturtle/exporter/base/setuphandlers.py
    """

    layer = REDTURTLE_IMPORTER_BASE_FUNCTIONAL_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.migration_view = api.content.get_view(
            name="data-migration", context=self.portal, request=self.request
        )
        self.request.form["_authenticator"] = createToken()
        api.content.delete(objects=self.portal.listFolderContents())

    def tearDown(self):
        """
        clear site
        """
        api.content.delete(objects=self.portal.listFolderContents())

    def test_base_migration_succeed(self):
        pc = api.portal.get_tool(name="portal_catalog")
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

    def test_correctly_set_dates(self):
        del os.environ["MIGRATION_FILE_PATH"]
        self.migration_view.do_migrate()

        published_document = api.content.get("/plone/first-document")
        private_document = api.content.find(
            portal_type="Document", review_state="private"
        )[0]

        self.assertEqual(published_document.effective().Date(), DateTime().Date())
        self.assertEqual(private_document.effective.Date(), "1969/12/31")

    def test_do_not_migrate_private_contents(self):
        os.environ["MIGRATION_FILE_PATH"] = get_config_file_path("skip_private.cfg")
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

    def test_import_users_and_groups(self):
        os.environ["MIGRATION_FILE_PATH"] = get_config_file_path(
            "import_users_and_groups.cfg"
        )

        self.assertEqual(len(api.user.get_users()), 1)
        self.assertEqual(len(api.group.get_groups()), 4)

        self.migration_view.do_migrate()

        self.assertEqual(len(api.user.get_users()), 3)
        self.assertEqual(len(api.group.get_groups()), 5)
        self.assertEqual(api.user.get_users(groupname="staff")[0].getId(), "bob")
        self.assertEqual(
            api.user.get_users(groupname="Administrators")[0].getId(), "john"
        )

        bob = api.user.get(username="bob")
        john = api.user.get(username="john")
        self.assertEqual(bob.getProperty("email"), "bob@plone.org")
        self.assertEqual(bob.getProperty("fullname"), "")
        self.assertEqual(bob.getProperty("home_page"), "")
        self.assertEqual(bob.getProperty("description"), "")

        self.assertEqual(john.getProperty("email"), "jdoe@plone.org")
        self.assertEqual(john.getProperty("fullname"), "John Doe")
        self.assertEqual(john.getProperty("home_page"), "http://www.plone.org")
        self.assertEqual(john.getProperty("description"), "foo")

    def test_import_in_custom_destination(self):
        os.environ["MIGRATION_FILE_PATH"] = get_config_file_path("custom_path.cfg")

        self.migration_view.do_migrate()

        children = self.portal.listFolderContents()
        documents = api.content.find(portal_type="Document")
        folders = api.content.find(portal_type="Folder")
        collections = api.content.find(portal_type="Collection")
        news = api.content.find(portal_type="News Item")
        files = api.content.find(portal_type="File")
        images = api.content.find(portal_type="Image")
        events = api.content.find(portal_type="Event")

        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].getId(), "custom-destination")
        self.assertEqual(len(documents), 4)
        self.assertEqual(len(folders), 7)
        self.assertEqual(len(collections), 3)
        self.assertEqual(len(news), 2)
        self.assertEqual(len(files), 1)
        self.assertEqual(len(images), 1)
        self.assertEqual(len(events), 1)

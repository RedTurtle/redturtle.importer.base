# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone import api
from redturtle.importer.base.testing import (
    REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING,  # noqa: E501
)
from redturtle.importer.base.browser.migrations import (
    RedTurtlePlone5MigrationMain,
)
from unittest.mock import patch

import unittest


USERS = {
    '_acl_users': {
        'bob': {
            'email': 'bob@plone.org',
            'properties': {'fullname': ''},
            'roles': ['Member', 'Authenticated'],
        },
        'john': {
            'email': 'jdoe@plone.org',
            'properties': {
                'fullname': 'John Doe',
                'description': 'foo',
                'home_page': 'http://www.google.it',
            },
            'roles': ['Member', 'Authenticated'],
        },
    }
}

GROUPS = {
    '_acl_groups': {
        "Administrators": {
            "roles": {"Manager": 1, "Authenticated": 1},
            "description": "",
            "members": ["john"],
            "title": "Administrators",
        },
        'staff': {
            'description': '',
            'members': ['bob'],
            'roles': {'Authenticated': 1, 'Editor': 1, 'Reader': 1},
            'title': '',
        },
    }
}


class TestImportUsersAndGroups(unittest.TestCase):
    """
    """

    layer = REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])

    def test_import_users_a(self):
        with patch.object(
            RedTurtlePlone5MigrationMain,
            'retrieve_json_from_remote',
            return_value=USERS,
        ):
            view = api.content.get_view(
                name='data-migration',
                context=self.portal,
                request=self.request,
            )

            self.assertEqual(len(api.user.get_users()), 1)
            view.import_users()
            self.assertEqual(len(api.user.get_users()), 3)
            bob = api.user.get(username='bob')
            john = api.user.get(username='john')
            self.assertEqual(
                bob.getProperty('email'), USERS['_acl_users']['bob']['email']
            )
            self.assertEqual(
                john.getProperty('email'), USERS['_acl_users']['john']['email']
            )
            self.assertEqual(
                bob.getProperty('fullname'),
                USERS['_acl_users']['bob']['properties']['fullname'],
            )
            self.assertEqual(
                john.getProperty('fullname'),
                USERS['_acl_users']['john']['properties']['fullname'],
            )
            self.assertEqual(bob.getProperty('home_page'), '')
            self.assertEqual(
                john.getProperty('home_page'),
                USERS['_acl_users']['john']['properties']['home_page'],
            )
            self.assertEqual(bob.getProperty('description'), '')
            self.assertEqual(
                john.getProperty('description'),
                USERS['_acl_users']['john']['properties']['description'],
            )

    def test_import_groups(self):
        with patch.object(
            RedTurtlePlone5MigrationMain,
            'retrieve_json_from_remote',
            return_value=GROUPS,
        ):
            view = api.content.get_view(
                name='data-migration',
                context=self.portal,
                request=self.request,
            )
            self.assertEqual(len(api.group.get_groups()), 4)
            view.import_groups()
            self.assertEqual(len(api.group.get_groups()), 5)
            self.assertEqual(len(api.user.get_users(groupname='staff')), 0)

    def test_import_users_and_groups(self):
        with patch.object(
            RedTurtlePlone5MigrationMain,
            'retrieve_json_from_remote',
            return_value=USERS,
        ):
            view = api.content.get_view(
                name='data-migration',
                context=self.portal,
                request=self.request,
            )
            view.import_users()

        self.assertNotIn('Manager', api.user.get_roles(username='john'))
        self.assertNotIn('Editor', api.user.get_roles(username='bob'))
        with patch.object(
            RedTurtlePlone5MigrationMain,
            'retrieve_json_from_remote',
            return_value=GROUPS,
        ):
            view = api.content.get_view(
                name='data-migration',
                context=self.portal,
                request=self.request,
            )
            view.import_groups()
        self.assertIn('Manager', api.user.get_roles(username='john'))
        self.assertIn('Editor', api.user.get_roles(username='bob'))
        self.assertEqual(
            api.user.get_users(groupname='staff')[0].getId(), 'bob'
        )
        self.assertEqual(
            api.user.get_users(groupname='Administrators')[0].getId(), 'john'
        )

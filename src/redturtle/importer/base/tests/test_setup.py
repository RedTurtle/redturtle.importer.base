# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from redturtle.importer.base.testing import REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING  # noqa

import unittest


class TestSetup(unittest.TestCase):
    """Test that redturtle.importer.base is properly installed."""

    layer = REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if redturtle.importer.base is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'redturtle.importer.base'))

    def test_browserlayer(self):
        """Test that IRedturtleImporterBaseLayer is registered."""
        from redturtle.importer.base.interfaces import (
            IRedturtleImporterBaseLayer)
        from plone.browserlayer import utils
        self.assertIn(
            IRedturtleImporterBaseLayer,
            utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')
        roles_before = api.user.get(userid=TEST_USER_ID).getRoles()  # noqa
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.installer.uninstallProducts(['redturtle.importer.base'])
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if redturtle.importer.base is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'redturtle.importer.base'))

    def test_browserlayer_removed(self):
        """Test that IRedturtleImporterBaseLayer is removed."""
        from redturtle.importer.base.interfaces import \
            IRedturtleImporterBaseLayer
        from plone.browserlayer import utils
        self.assertNotIn(
            IRedturtleImporterBaseLayer,
            utils.registered_layers())

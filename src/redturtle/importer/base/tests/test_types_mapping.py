# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from redturtle.importer.base.interfaces import IPortalTypeMapping
from redturtle.importer.base.testing import REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING
from zope.component import subscribers

import unittest


class TestTypesMapping(unittest.TestCase):
    """
    """

    layer = REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def apply_handlers(self, item):
        handlers = [
            x for x in subscribers((self.portal, self.request), IPortalTypeMapping)
        ]
        for handler in sorted(handlers, key=lambda h: h.order):
            item = handler(item=item, typekey="_type")
        return item

    def test_links_internal_link_converter(self):
        item = {"_type": "Link", "internalLink": "foo"}

        result = self.apply_handlers(item=item)

        self.assertIn("remoteUrl", result.keys())
        self.assertEqual(result["remoteUrl"], "${portal_url}/resolveuid/foo")

    def test_links_external_link_converter(self):
        item = {"_type": "Link", "remoteUrl": "foo"}

        result = self.apply_handlers(item=item)

        self.assertIn("remoteUrl", result.keys())
        self.assertEqual(result["remoteUrl"], "foo")

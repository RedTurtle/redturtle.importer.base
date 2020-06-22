# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2
from time import sleep

import redturtle.importer.base
import six
import sys


class RedturtleImporterBaseLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.

        self.loadZCML(package=redturtle.importer.base)

    def setUp(self):
        """
        wait until docker image is ready
        """
        ping_url = "http://127.0.0.1:8080/Plone"
        for i in range(1, 10):
            try:
                result = six.moves.urllib.request.urlopen(ping_url)
                if result.code == 200:
                    break
            except six.moves.urllib.error.URLError:
                sleep(3)
                sys.stdout.write(".")
            if i == 9:
                sys.stdout.write("Docker Instance could not be started !!!")

        super(RedturtleImporterBaseLayer, self).setUp()


REDTURTLE_IMPORTER_BASE_FIXTURE = RedturtleImporterBaseLayer()

REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(REDTURTLE_IMPORTER_BASE_FIXTURE,),
    name="RedturtleImporterBaseLayer:IntegrationTesting",
)


REDTURTLE_IMPORTER_BASE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(REDTURTLE_IMPORTER_BASE_FIXTURE,),
    name="RedturtleImporterBaseLayer:FunctionalTesting",
)


REDTURTLE_IMPORTER_BASE_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        REDTURTLE_IMPORTER_BASE_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="RedturtleImporterBaseLayer:AcceptanceTesting",
)

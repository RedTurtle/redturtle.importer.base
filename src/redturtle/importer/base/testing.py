# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import redturtle.importer.base


class RedturtleImporterBaseLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        self.loadZCML(package=redturtle.importer.base)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'redturtle.importer.base:default')


REDTURTLE_IMPORTER_BASE_FIXTURE = RedturtleImporterBaseLayer()


REDTURTLE_IMPORTER_BASE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(REDTURTLE_IMPORTER_BASE_FIXTURE,),
    name='RedturtleImporterBaseLayer:IntegrationTesting'
)


REDTURTLE_IMPORTER_BASE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(REDTURTLE_IMPORTER_BASE_FIXTURE,),
    name='RedturtleImporterBaseLayer:FunctionalTesting'
)


REDTURTLE_IMPORTER_BASE_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        REDTURTLE_IMPORTER_BASE_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE
    ),
    name='RedturtleImporterBaseLayer:AcceptanceTesting'
)

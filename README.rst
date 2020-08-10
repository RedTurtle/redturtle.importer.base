=======================
RedTurtle importer base
=======================

Tool to migrate contents between Plone sites based on transmogrifier.

This tool works in addition with `redturtle.exporter.base`__

__ https://pypi.org/project/redturtle.exporter.base


Dependencies
============

This product is made over other useful tools:

* `collective.jsonmigrator`__
* `collective.transmogrifier`__
* `transmigrify.dexterity`__

__ https://github.com/collective/collective.jsonmigrator
__ https://github.com/collective/collective.transmogrifier
__ https://github.com/collective/transmogrify.dexterity

These tools are not yet actively maintained, so we moved useful parts into this
project to have a working Python 3 importer based on transmogrifier.


Features
========

- Handle migration for basic content-types
- Discussions migration
- Customizable import procedure via blueprints
- Extensible with more specific blueprints
- Possibility to customize specific step options with custom adapters
- Review view after migration with process results

Installation
============

Install redturtle.importer.base by adding it to your buildout::

    [buildout]

    ...

    eggs =
        redturtle.importer.base


and then running ``bin/buildout``

You don't have to install it. In this way, after the data migration, you can
remove it from the buildout and everything is clean.


Usage
=====

Migration view
--------------
To start a migration, you only need to call `@@data-migration` view on site root.

In this view you can see the blueprint configuration (base and overrided), and start the process.

Pipelines customization
-----------------------

This tool is based on transmogrifier and works with blueprints.
A blueprint is basically a config file that lists all the steps needed for the migration.

This product has a `default blueprint`__ for basic migrations, that can be used as is.

Default blueprint can be easily customized using a `.migrationconfig.cfg` file located in buildout root folder.

In this file you can override already present parts/variables (like `pipelines` into `[transmogrifier]` section) or 
add new ones (for example a new step).

For example, catalogsource step can be configured with some queries like this::

    [catalogsource]
    catalog-query = {'portal_type': ['Document', 'Event', 'News Item']}
    ...

In `.migrationconfig.cfg` file, under `[catalogsource]` section, you also need to set some settings about how to retrieve data on source site::

    [catalogsource]
    ...
    remote-url = http://localhost:8080
    remote-root = /Plone
    catalog-path = /Plone/portal_catalog
    remote-username = username
    remote-password = password
    ...


Before running a migration, you can check the final configuration in `@@data-migration` view.


__ https://github.com/RedTurtle/redturtle.importer.base/blob/python3/src/redturtle/importer/base/transmogrifier/redturtleplone5.cfg


catalogsource configuration
---------------------------

This is an example of `[catalogsource]` part::
 
    [catalogsource]
    ...
    remote-url = http://localhost:8080
    remote-root = /Plone
    catalog-path = /Plone/portal_catalog
    remote-username = username
    remote-password = password

Required options are:

- `remote-url`: The url of source Plone site
- `remote-root`: The path of Plone site that we want to migrate
- `remote-username`: Credentials to access to source site
- `remote-password`: Credentials to access to source site

Additional options are:

- `default-local-path`: A path where save migrate contents in destination Site. This path will replace item's root path. Destination root path is not needed in this path.
- `skip-private`: Boolean to migrate or not private items into destination. Default is `False`.
- `remote_skip_paths`: A list of paths from source site that will be skipped during migration process.
- `incremental-migration`: Boolean value. If a content already migrate hasn't been modified since last migration, don't override it. Default is `False`.
- `ignore-cache`: Boolean value. If True, ignore local cache and always get content data from source site.
- `cache-dir`: Local folder where migration data cache will be stored. Default is `/tmp/migration/migration_cache`.
- `migration-dir`: Local fodler where migration support files (for final summary for example) will be saved. Default is '/tmp/migration'.


Custom types mapping
--------------------

*contentsmapping* is the section that allows to convert one portal_type to another before object creation.

There is a plugin system based on subscribers that allows plugins to add custom mappings.

You need to register a subscriber for `IPortalTypeMapping` like this::

    <subscriber
        factory=".types_mapping.MyCustomMapping"
        provides="redturtle.importer.base.interfaces.IPortalTypeMapping"/>

And then you need to create the class::

    @adapter(IPloneSiteRoot, IBrowserRequest)
    @implementer(IPortalTypeMapping)
    class MyCustomMapping(object):
        order = 100

        def __init__(self, context, request):
            self.context = context
            self.request = request

        def __call__(self, item, typekey):
            """
            """
            portal_type = item[typekey]
            if portal_type == "Type-A":
                item[typekey] = "Type-B"
                ...
            return item


Custom steps for specific portal types
--------------------------------------

If you are migrating a content-type that needs some manual fixes after the creation, you can do it with an adapter.

You only need to register an adapter for your content-type like this::

    <adapter
      for="my.product.interfaces.IMyInterface"
      provides="redturtle.importer.base.interfaces.IMigrationContextSteps"
      factory=".steps.MyTypeSteps"
    />


And then you need to provide a "doSteps" method in the class::

    from redturtle.importer.base.interfaces import IMigrationContextSteps
    from zope.interface import implementer

    @implementer(IMigrationContextSteps)
    class MyTypeSteps(object):

        def __init__(self, context):
            self.context = context

        def doSteps(self):
            """
            do something here
            """

Example specific importers
==========================

There are some per-project importers that we used to migrate some projects and you can use them as a starting point
to develop new ones.

They are basically packages that you need to include in your buildout and provides some custom steps for specific types:

- `redturtle.importer.rer`__
- `redturtle.importer.volto`__

__ https://github.com/RedTurtle/redturtle.importer.rer
__ https://github.com/RedTurtle/redturtle.importer.volto


Import Users and groups
=======================

You can also import users and groups from source site.

You only need to add a section to your migration config file like this::

    [users_and_groups]
    import-users = True
    import-groups = True

The tool will call two views from source site and will use the settings 
(remote-url, remote-root and credentials) from *[catalogsource]* section.

This import is performed after transmogrifier steps.


Contribute
==========

- Issue Tracker: https://github.com/RedTurtle/redturtle.importer.base/issues
- Source Code: https://github.com/RedTurtle/redturtle.importer.base

Credits
=======

This product has been developed with some help from

.. image:: https://kitconcept.com/logo.svg
   :alt: kitconcept
   :width: 300
   :height: 80
   :target: https://kitconcept.com/

License
=======

The project is licensed under the GPLv2.

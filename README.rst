=======================
RedTurtle importer base
=======================

Tool to migrate contents between Plone sites based on transmogrifier.

Dependencies
============

This product is made over other useful tools:

* `collective.jsonmigrator`__
* `transmigrify.dexterity`__

__ https://github.com/collective/collective.jsonmigrator
__ https://github.com/collective/transmogrify.dexterity

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


Custom steps and mappings
-------------------------

TODO


Cache
-----

TODO

Incremental migration
---------------------

TODO


Contribute
==========

- Issue Tracker: https://github.com/RedTurtle/redturtle.importer.base/issues
- Source Code: https://github.com/RedTurtle/redturtle.importer.base


License
=======

The project is licensed under the GPLv2.

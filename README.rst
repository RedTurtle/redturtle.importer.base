.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on pypi or github. It is a comment.

==================
RedTurtle importer
==================

A content-type importer from a source site

Dependencies
============

This product is made over other useful tools:

* `ploneorg.migration`__
* `transmigrify.dexterity`__

__ https://github.com/collective/ploneorg.migration
__ https://github.com/collective/transmogrify.dexterity

Features
========

- Handle migration for basic content-types
- Discussions migration
- Customizable export procedure via blueprints
- Extensible with more specific blueprints
- Possibility to customize specific step options with custom cfg file
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
In this view you can see which parameters are customized (via cfg file), and start the process.

Customize steps parameters
--------------------------

This tool is based on transmogrifier and works with blueprints.
A blueprint is basically a config file that lists all the steps needed for the migration.

This product has a default blueprint for basic migrations, that can be used as is.
You could also use different blueprints in custom packages (see above).

Each step could be configured with a different set of parameters. You could override standard ones with a config file in buildout's root.

That file should be called `.migrationconfig.cfg` and could have different sections (one per step).

For example, catalogsource step can be configured with some queries like this::

    [catalogsource]
    catalog-query = {'portal_type': ['Document', 'Event', 'News Item']}
    ...

Source site access
------------------

In `.migrationconfig.cfg` file, under `[catalogsource]` section, you also need to set some settings about how to retrieve data on source site::

    [catalogsource]
    ...
    remote-url = http://localhost:8080
    remote-root = /Plone
    catalog-path = /Plone/portal_catalog
    remote-username = username
    remote-password = password
    ...


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

# -*- coding: utf-8 -*-
from DateTime import DateTime
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import traverse
from zope.interface import provider
from zope.interface import implementer


@provider(ISectionBlueprint)
@implementer(ISection)
class DatesUpdater(object):
    """Sets creation and modification dates on objects.
    """

    def __init__(self, transmogrifier, name, options, previous):
        """
        :param options['path-key']: The key, under the path can be found in
                                    the item.
        :param options['creation-key']: Creation date key. Defaults to
                                        creation_date.
        :param options['modification-key']: Modification date key. Defaults to
                                            modification_date.
        :param options['effective-key']: Effective date key. Defaults to
                                            effective_date.
        :param options['expiration-key']: Expiration date key. Defaults to
                                            expiration_date.
        """
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.creationkey = options.get('creation-key', 'creation_date')
        self.modificationkey = options.get('modification-key', 'modification_date')  # noqa
        self.effectivekey = options.get('effective-key', 'effective_date')
        self.expirationkey = options.get('expiration-key', 'expiration_date')

    def __iter__(self):

        for item in self.previous:

            pathkey = self.pathkey(*list(item.keys()))[0]
            if not pathkey:  # not enough info
                yield item
                continue
            path = item[pathkey]

            ob = traverse(self.context, str(path).lstrip('/'), None)
            if ob is None:
                yield item
                continue  # object not found

            creationdate = item.get(self.creationkey, None)
            if creationdate and hasattr(ob, 'creation_date'):
                ob.creation_date = DateTime(creationdate)

            modificationdate = item.get(self.modificationkey, None)
            if modificationdate and hasattr(ob, 'modification_date'):
                ob.modification_date = DateTime(modificationdate)

            effectivedate = item.get(self.effectivekey, None)
            if effectivedate and hasattr(ob, 'effective_date'):
                ob.effective_date = DateTime(effectivedate)

            expirationdate = item.get(self.expirationkey, None)
            if expirationdate and hasattr(ob, 'expiration_date'):
                ob.expiration_date = DateTime(expirationdate)

            yield item

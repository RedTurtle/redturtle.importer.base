# -*- coding: utf-8 -*-
from __future__ import print_function
from plone import api
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import Condition
from redturtle.importer.base.transmogrifier.utils import Expression
from redturtle.importer.base import logger
from six.moves import zip
from zope.annotation.interfaces import IAnnotations
from zope.interface import provider
from zope.interface import implementer

import six


VALIDATIONKEY = "redturtle.importer.base.logger"


@implementer(ISection)
@provider(ISectionBlueprint)
class PathManipulator(object):

    """ This allows to modify the path parts given a template in the template
        variable.

        given a path: first/second/third/fourth

        and we want to change all the items that match the condition to:

        first_modified(and fixed)/second/fourth

        the template will be:

        template = string:first_fixed/=//=

        using = to determinate that we want the same string in that path part,
        and using nothing for parts that we no longer want to include.

        One (*) wilcard can be included to note that any middle paths can be
        used with no changes.
    """

    def __init__(self, transmogrifier, name, options, previous):
        # self.key = Expression(options['key'], transmogrifier, name, options)
        self.template = Expression(
            options["template"], transmogrifier, name, options
        )
        # self.value = Expression(options['value'], transmogrifier, name,
        #                         options)
        self.condition = Condition(
            options.get("condition", "python:True"),
            transmogrifier,
            name,
            options,
        )
        self.previous = previous

        self.available_operators = ["*", "", "="]

        self.anno = IAnnotations(api.portal.get().REQUEST)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])

    def __iter__(self):
        for item in self.previous:
            template = six.text_type(self.template(item))
            result_path = [""]
            if self.condition(item, key=template):
                original_path = item["_path"].split("/")
                # Save the original_path in the item
                item["_original_path"] = "/".join(original_path)
                template = template.split("/")
                if len(original_path) != len(template) and (
                    "*" not in template or "**" not in template
                ):
                    logger.debug(
                        "The template and the length of the path is not the"
                        "same nad there is no wildcards on it"
                    )
                    yield item

                # One to one substitution, no wildcards
                if (
                    len(original_path) == len(template)
                    and u"*" not in template
                    and u"**" not in template
                ):
                    actions = list(zip(original_path, template))
                    for p_path, operator in actions:
                        if operator not in self.available_operators:
                            # Substitute one string for the other
                            result_path.append(operator)
                        elif operator == "=":
                            result_path.append(p_path)
                        elif operator == "":
                            pass

                # We only attend to the number of partial paths before and
                # after the wildcard
                if u"*" in template or u"**" in template:
                    index = template.index(u"*")
                    # Process the head of the path (until wildcard)
                    head = list(zip(original_path, template[:index]))
                    for p_path, operator in head:
                        if operator not in self.available_operators:
                            # Substitute one string for the other
                            result_path.append(operator)
                        elif operator == "=":
                            result_path.append(p_path)
                        elif operator == "":
                            pass

                    # Need to know how many partial paths we have to copy (*)
                    tail_path_length = len(template[index:]) - 1
                    for p_path in original_path[index:-tail_path_length]:
                        result_path.append(p_path)

                    # Process the tail of the path (from wildcard)
                    original_path_reversed = list(original_path)
                    original_path_reversed.reverse()
                    tail = list(
                        zip(
                            original_path_reversed, template[-tail_path_length]
                        )
                    )

                    # Complete the tail
                    for p_path, operator in tail:
                        if operator not in self.available_operators:
                            # Substitute one string for the other
                            result_path.append(operator)
                        elif operator == "=":
                            result_path.append(p_path)
                        elif operator == "":
                            pass

                # Update storage item counter path (for logging)
                if item["_path"] in self.storage:
                    self.storage.remove(item["_path"])
                    self.storage.append("/".join(result_path))

                # Update item path
                item["_path"] = "/".join(result_path)

            yield item

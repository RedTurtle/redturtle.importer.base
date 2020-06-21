# -*- coding: utf-8 -*-
from __future__ import print_function
from Acquisition import aq_base
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultMatcher
from zope.container.contained import notifyContainerModified
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class OrderSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.every = int(options.get("every", 1000))
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, "path-key", name, "path")
        self.poskey = defaultMatcher(options, "pos-key", name, "gopip")
        # Position of items without a position value
        self.default_pos = int(options.get("default-pos", 1000000))

    def __iter__(self):
        # Store positions in a mapping containing an id to position mapping for
        # each parent path {parent_path: {item_id: item_pos}}.
        positions_mapping = {}
        for item in self.previous:
            keys = list(item.keys())
            pathkey = self.pathkey(*keys)[0]
            poskey = self.poskey(*keys)[0]

            if not (pathkey and poskey):
                yield item
                continue

            item_id = item[pathkey].split("/")[-1]
            parent_path = "/".join(item[pathkey].split("/")[:-1])
            if parent_path not in positions_mapping:
                positions_mapping[parent_path] = {}
            positions_mapping[parent_path][item_id] = item[poskey]

            yield item

        # Set positions on every parent
        for path, positions in positions_mapping.items():

            # Normalize positions
            ordered_keys = sorted(
                list(positions.keys()), key=lambda x: positions[x]
            )
            normalized_positions = {}
            for pos, key in enumerate(ordered_keys):
                normalized_positions[key] = pos

            # TODO: After the new redturtle.importer.base release (>1.4), the
            # utils.py provides a traverse method.
            from redturtle.importer.base.transmogrifier.utils import traverse

            parent = traverse(self.context, path)
            # parent = self.context.unrestrictedTraverse(path.lstrip('/'))
            if not parent:
                continue

            parent_base = aq_base(parent)

            if getattr(parent_base, "getOrdering", None):
                ordering = parent.getOrdering()
                # Only DefaultOrdering of p.folder is supported
                if not getattr(ordering, "_order", None) and not getattr(
                    ordering, "_pos", None
                ):
                    continue
                order = ordering._order()
                pos = ordering._pos()
                order.sort(
                    key=lambda x: normalized_positions.get(
                        x, pos.get(x, self.default_pos)
                    )
                )
                for i, id_ in enumerate(order):
                    pos[id_] = i

                notifyContainerModified(parent)

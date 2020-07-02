# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import Matcher
from copy import deepcopy
from DateTime import DateTime
from plone import api
from plone.dexterity.interfaces import IDexterityContent
from redturtle.importer.base import logger
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class WorkflowHistory(object):
    """
    """

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.wftool = api.portal.get_tool(name="portal_workflow")

        if "path-key" in options:
            pathkeys = options["path-key"].splitlines()
        else:
            pathkeys = defaultKeys(options["blueprint"], name, "path")
        self.pathkey = Matcher(*pathkeys)

        if "workflowhistory-key" in options:
            workflowhistorykeys = options["workflowhistory-key"].splitlines()
        else:
            workflowhistorykeys = defaultKeys(
                options["blueprint"], name, "workflow_history"
            )
        self.workflowhistorykey = Matcher(*workflowhistorykeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            workflowhistorykey = self.workflowhistorykey(*list(item.keys()))[0]

            if (
                not pathkey
                or not workflowhistorykey
                or workflowhistorykey not in item
            ):  # not enough info
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip("/"), None
            )
            if obj is None or not getattr(obj, "workflow_history", False):
                yield item
                continue

            if IDexterityContent.providedBy(obj):
                item_tmp = deepcopy(item)
                wf_list = self.wftool.getWorkflowsFor(obj)
                if not wf_list:

                    yield item
                    continue

                current_obj_wf = wf_list[0].id

                # At least copy the previous history to the
                # new workflow (if not the same)
                # Asuming one workflow
                try:
                    item_tmp[workflowhistorykey].update(
                        {
                            current_obj_wf: item_tmp[workflowhistorykey][
                                list(item_tmp[workflowhistorykey].keys())[0]
                            ]
                        }
                    )  # noqa
                except Exception:
                    logger.debug(
                        u"Failed to copy history to the new"
                        u" workflow for {0}".format(item["_path"])
                    )
                    pass
                # In case that we need to change internal state names
                # wf_hist_temp = deepcopy(item[workflowhistorykey])
                # for workflow in wf_hist_temp:
                #     # Normalize workflow
                #     if workflow == u'genweb_review':
                #         for k, workflow2 in enumerate(item_tmp[workflowhistorykey]['genweb_review']):  # noqa
                #             if 'review_state' in item_tmp[workflowhistorykey]['genweb_review'][k]:  # noqa
                #                 if item_tmp[workflowhistorykey]['genweb_review'][k]['review_state'] == u'esborrany':  # noqa
                #                     item_tmp[workflowhistorykey]['genweb_review'][k]['review_state'] = u'visible'  # noqa
                #
                #         item_tmp[workflowhistorykey]['genweb_simple'] = item_tmp[workflowhistorykey]['genweb_review']  # noqa
                #         del item_tmp[workflowhistorykey]['genweb_review']

                # get back datetime stamp and set the workflow history
                for workflow in item_tmp[workflowhistorykey]:
                    for k, workflow2 in enumerate(
                        item_tmp[workflowhistorykey][workflow]
                    ):  # noqa
                        if "time" in item_tmp[workflowhistorykey][workflow][k]:
                            item_tmp[workflowhistorykey][workflow][k][
                                "time"
                            ] = DateTime(  # noqa
                                item_tmp[workflowhistorykey][workflow][k][
                                    "time"
                                ]
                            )  # noqa

                obj.workflow_history.data = item_tmp[workflowhistorykey]

                # update security
                workflows = self.wftool.getWorkflowsFor(obj)
                if workflows:
                    workflows[0].updateRoleMappingsFor(obj)

            yield item

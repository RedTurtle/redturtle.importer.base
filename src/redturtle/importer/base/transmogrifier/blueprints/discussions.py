# -*- coding: utf-8 -*-
from __future__ import print_function
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import defaultKeys
from redturtle.importer.base.transmogrifier.utils import Matcher
from DateTime import DateTime
from plone.app.discussion.comment import CommentFactory
from plone.app.discussion.interfaces import IConversation
from redturtle.importer.base import logger
from zope.interface import provider
from zope.interface import implementer


@implementer(ISection)
@provider(ISectionBlueprint)
class Discussions(object):
    """A blueprint for importing comments into plone
    """

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        if "path-key" in options:
            pathkeys = options["path-key"].splitlines()
        else:
            pathkeys = defaultKeys(options["blueprint"], name, "parent_path")
        self.pathkey = Matcher(*pathkeys)
        if "comment-type-key" in options:
            comment_type_keys = options["comment-type-key"].splitlines()
        else:
            comment_type_keys = defaultKeys(
                options["blueprint"], name, "comment_type"
            )
        self.comment_type_key = Matcher(*comment_type_keys)
        self.date_format = options.get("date-format", "%Y/%m/%d %H:%M:%S")

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*list(item.keys()))[0]
            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(
                str(path).lstrip("/"), None
            )
            # path doesn't exist
            if obj is None:
                yield item
                continue
            discussion = item.get("discussions", [])
            if not discussion:
                yield item
                continue

            id_map = {}
            conversation = IConversation(obj)

            # remove all comments to avoid duplication when override is disabled  # noqa
            if list(conversation.items()):
                comments_id = [x[0] for x in conversation.items()]
                for value in comments_id:
                    try:
                        del conversation[value]
                    except Exception:
                        logger.warning(
                            "WARNING: Discussion with id {0} not found".format(  # noqa
                                value
                            )
                        )
                        pass

            for comment in discussion:
                new_comment = CommentFactory()

                new_comment.text = comment.get("text")
                new_comment.creator = comment.get("creator")
                new_comment.author_name = comment.get("author_name")
                new_comment.author_username = comment.get("author_username")
                new_comment.author_email = comment.get("author_email")
                new_comment.in_reply_to = id_map.get(
                    comment.get("in_reply_to"), 0
                )
                new_comment.mime_type = comment.get("mime_type")
                new_comment._owner = comment.get("_owner")
                new_comment.__ac_local_roles__ = comment.get(
                    "__ac_local_roles__"
                )
                new_comment.user_notification = comment.get(
                    "user_notification"
                )
                new_comment.creation_date = DateTime(
                    comment.get("creation_date")
                ).asdatetime()
                new_comment.modification_date = DateTime(
                    comment.get("modification_date")
                ).asdatetime()

                conversation.addComment(new_comment)

                comment_wf = new_comment.workflow_history.data.get(
                    "comment_review_workflow"
                )
                if comment_wf:
                    new_comment.workflow_history.data.get(
                        "comment_review_workflow"
                    )[  # noqa
                        0
                    ][
                        "review_state"
                    ] = comment[
                        "status"
                    ]

                id_map.update(
                    {comment.get("comment_id"): int(new_comment.comment_id)}
                )

                logger.info(
                    (
                        "Added comment with id {0} to item {1}".format(
                            new_comment.comment_id, obj.absolute_url()
                        )
                    )
                )
            yield item

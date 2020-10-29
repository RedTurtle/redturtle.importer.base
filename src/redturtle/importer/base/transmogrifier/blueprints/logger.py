# -*- coding: utf-8 -*-
from plone import api
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import Matcher
from redturtle.importer.base.transmogrifier.utils import COUNTKEY
from redturtle.importer.base.transmogrifier.utils import ERROREDKEY
from redturtle.importer.base.transmogrifier.utils import VALIDATIONKEY
from time import time
from zope.annotation.interfaces import IAnnotations
from zope.interface import provider, implementer


import logging


@implementer(ISection)
@provider(ISectionBlueprint)
class LoggerSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        keys = options.get("keys") or ""
        self.pathkey = options.get("path-key", "_path").strip()
        self.keys = Matcher(*keys.splitlines())
        self.previous = previous
        self.logger = name

        self.storage = IAnnotations(api.portal.get().REQUEST).setdefault(
            VALIDATIONKEY, []
        )
        self.errored = IAnnotations(api.portal.get().REQUEST).setdefault(ERROREDKEY, [])
        self.count = IAnnotations(api.portal.get().REQUEST).setdefault(COUNTKEY, {})

    def __iter__(self):
        start_time = time()
        count = 0
        problematic = 0
        problematic2 = 0
        for item in self.previous:
            # source sections add store path of current generated item in annotation
            # it gives posibility to monitor what items go through all pipeline
            # sections between source section and this section and what don't
            if self.pathkey in item and item[self.pathkey] in self.storage:
                self.storage.remove(item[self.pathkey])
            count += 1
            # print item data stored on keys given as option
            items = []
            for key in item.keys():
                if self.keys(key)[0] is not None:
                    items.append("%s=%s" % (key, item[key]))
            if items:
                msg = ", ".join(items)
                logging.getLogger(self.logger).info(msg)

                self.count["remaining"] = self.count["remaining"] - 1
                logging.getLogger(self.logger).info(
                    "Remaining {} of {}.".format(
                        self.count["remaining"], self.count["total"]
                    )
                )

            yield item

        working_time = int(round(time() - start_time))

        # log items that maybe have some problems
        if self.storage:
            problematic = len(self.storage)
            logging.getLogger(self.logger).warning(
                "\nNext objects didn't go through full pipeline:\n%s"
                % "\n".join(["\t" + i for i in self.storage])
            )
        if self.errored:
            problematic2 = len(self.errored)
            logger = logging.getLogger(self.logger)
            logger.warning("\nNext objects errored somewhere in the pipeline:")
            for error in self.errored:
                logger.warning(
                    "- {path}: {reason}".format(
                        path=error["path"], reason=error.get("reason", "")
                    )
                )
            # self.log_errors(self.errored)
        # delete validation data from annotations
        annotations = IAnnotations(api.portal.get().REQUEST)
        if VALIDATIONKEY in annotations:
            del annotations[VALIDATIONKEY]
        if ERROREDKEY in annotations:
            del annotations[ERROREDKEY]

        seconds = working_time % 60
        minutes = working_time / 60 % 60
        hours = working_time / 3600
        stats = "\nPipeline processing time: %02d:%02d:%02d\n" % (
            hours,
            minutes,
            seconds,
        )
        stats += "\t%4d items were generated in source sections\n" % (
            count + problematic
        )
        stats += "\t%4d went through full pipeline\n" % count
        stats += "\t%4d were discarded in some section\n" % problematic
        stats += "\t%4d were errored in some section" % problematic2
        logging.getLogger(self.logger).info(stats)

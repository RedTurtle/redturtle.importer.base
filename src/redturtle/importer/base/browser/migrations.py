# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from Acquisition import aq_base
from collective.transmogrifier.transmogrifier import Transmogrifier
from lxml import etree
from plone import api
from plone.app.textfield import RichText
from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import iterSchemata
from plone.outputfilters.filters.resolveuid_and_caption import resolveuid_re
from Products.Five.browser import BrowserView
from redturtle.importer.base import logger
from redturtle.importer.base.utils import get_additional_config
from redturtle.importer.base.utils import get_base_config
from transmogrify.dexterity.interfaces import IDeserializer
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.schema import getFieldsInOrder

import errno
import json
import os


class RedTurtlePlone5MigrationMain(BrowserView):
    """
    Migration view
    """

    transmogrifier_conf = "redturtle.plone5.main"
    skip_types_in_link_check = ["Discussion Item"]

    def __call__(self):
        if not self.request.form.get("confirm", False):
            return self.index()

        return self.do_migrate()

    def do_migrate(self, REQUEST=None):

        authenticator = api.content.get_view(
            context=api.portal.get(),
            request=self.request,
            name=u"authenticator",
        )
        if not authenticator.verify():
            raise Unauthorized

        self.cleanup_log_files()
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier(self.transmogrifier_conf)

        # nel transmogrifier c'e' una lista di tuple:
        # (path, fieldname, value) per le quali vanno rifatte le relations
        for (path, fieldname, value) in getattr(
            transmogrifier, "fixrelations", []
        ):  # noqa
            logger.info("fix {0} {1} {2}".format(path, fieldname, value))
            obj = self.context.unrestrictedTraverse(path)
            for schemata in iterSchemata(obj):
                for name, field in getFieldsInOrder(schemata):
                    if name == fieldname:
                        if isinstance(value, basestring):
                            value = uuidToObject(value)
                        else:
                            value = [uuidToObject(uuid) for uuid in value]
                        deserializer = IDeserializer(field)
                        value = deserializer(value, [], {}, True, logger=logger)
                        # self.disable_constraints,
                        # logger=self.log,
                        field.set(field.interface(obj), value)
                        notify(ObjectModifiedEvent(obj))

        # run scripts after migration
        self.scripts_post_migration()
        logger.info("Migration done.")
        api.portal.show_message(
            message="Migration done. Check logs for a complete report."
            "Scripts after migration running....",
            request=self.request,
        )
        return self.request.response.redirect(
            "{0}/migration-results".format(api.portal.get().absolute_url())
        )

    def scripts_post_migration(self):
        self.generate_broken_links_list()
        self.fix_link_noreference()

    def cleanup_log_files(self):
        for type, section in [("in", "catalogsource"), ("out", "results")]:
            additional_config = get_additional_config(section=section)
            config = get_base_config(section=section)
            config.update(additional_config)
            file_name = config.get(
                "file-name-{0}".format(type),
                "migration_content_{0}.json".format(type),
            )
            file_path = "{0}/{1}_{2}".format(
                config.get("migration-dir"), api.portal.get().getId(), file_name
            )
            try:
                os.remove(file_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    # re-raise exception if a different error occurred
                    raise

    def get_config(self):
        return get_additional_config(all=True)

    def generate_broken_links_list(self):
        logger.info("Generating broken tinymce internal links.")
        pc = api.portal.get_tool(name="portal_catalog")
        brains = pc()
        broken_urls = []

        for brain in brains:
            if brain.portal_type in self.skip_types_in_link_check:
                continue
            item = aq_base(brain.getObject())
            for schemata in iterSchemata(item):
                for name, field in getFieldsInOrder(schemata):
                    if not isinstance(field, RichText):
                        continue
                    item_field = getattr(item, name, None)
                    if not item_field:
                        continue
                    raw_text = item_field.raw
                    if not raw_text:
                        continue
                    xml = etree.HTML(raw_text)
                    for link in xml.xpath("//a"):
                        match = resolveuid_re.match(link.get("href", ""))
                        if not match:
                            continue
                        uid, _subpath = match.groups()
                        obj = api.content.get(UID=uid[:32])
                        if not obj:
                            url = brain.getURL()
                            if url not in broken_urls:
                                broken_urls.append(url)
        self.write_broken_links(broken_urls)

    def write_broken_links(self, paths):
        additional_config = get_additional_config(section="results")
        config = get_base_config(section="results")
        config.update(additional_config)
        file_name = config.get("broken-links-tiny")
        file_path = "{0}/{1}_{2}".format(
            config.get("migration-dir"), api.portal.get().getId(), file_name
        )
        with open(file_path, "w") as fp:
            json.dump(paths, fp)

    def check_link_exist(self, link, link_path):
        result = True
        remote_site = get_additional_config(section="catalogsource")['remote-root']
        try:
            if remote_site not in link_path:
                return True
        except:
            if not link.internal_link.to_id:
                return False
            return True
            
        link_to_check_path = '%s' % (link_path.split(remote_site)[1])
        if not api.content.get(path=link_to_check_path):
            result = False
        return result

    def fix_link_noreference(self):
        logger.info("Generating noreference links.")
        noreference_urls = []
        brains = api.content.find(portal_type='Link')
        print 'Found {0} items.'.format(len(brains))
        for brain in brains:
            no_remote = True
	    no_internal = True

            link = brain.getObject()

            if link.remoteUrl:
                if not self.check_link_exist(link, link.remoteUrl):
                    no_remote = True
                else:
                    no_remote = False
 
            if link.internal_link:
                if not self.check_link_exist(link, link.internal_link):
                    no_internal = True
                else:
                    no_internal = False 

            if no_remote and no_internal:
                noreference_urls.append(link.absolute_url())
                logger.warn('Removing {0}'.format(link.absolute_url()))
                try:
                    api.content.delete(link)
                except KeyError:
                    logger.error('Cannot remove {0}'.format(link.absolute_url()))

        self.write_noreference_links(noreference_urls)

    def write_noreference_links(self, paths):
        additional_config = get_additional_config(section="results")
        config = get_base_config(section="results")
        config.update(additional_config)
        file_name = config.get("noreference-links")
        file_path = "{0}/{1}_{2}".format(
            config.get("migration-dir"), api.portal.get().getId(), file_name
        )
        with open(file_path, "w") as fp:
            json.dump(paths, fp)

class MigrationResults(BrowserView):
    """
    read debug files and expose statistics
    """

    def get_results(self):
        in_json = self.get_json_data(type="in", section="catalogsource")
        out_json = self.get_json_data(type="out", section="results")

        results = {
            "in_count": len(in_json.keys()),
            "out_count": len(out_json.keys()),
            "broken_links": self.get_broken_links(),
            "noreference_links": self.get_noreference_links(),
        }

        if out_json.keys() == in_json.keys():
            results["same_results"] = True
        else:
            results["same_results"] = False
            diff_keys = set(in_json.keys()) - set(out_json.keys())
            results["not_migrated"] = [in_json[k] for k in diff_keys]

        return results

    def get_json_data(self, type, section):
        additional_config = get_additional_config(section=section)
        config = get_base_config(section=section)
        config.update(additional_config)
        file_name = config.get(
            "file-name-{0}".format(type),
            "migration_content_{0}.json".format(type),
        )
        file_path = "{0}/{1}_{2}".format(
            config.get("migration-dir"), api.portal.get().getId(), file_name
        )
        with open(file_path, "r") as fp:
            return json.loads(fp.read())

    def get_broken_links(self):
        additional_config = get_additional_config(section="results")
        config = get_base_config(section="results")
        config.update(additional_config)
        file_name = config.get("broken-links-tiny")
        file_path = "{0}/{1}_{2}".format(
            config.get("migration-dir"), api.portal.get().getId(), file_name
        )
        with open(file_path, "r") as fp:
            return json.loads(fp.read())

    def get_noreference_links(self):
        additional_config = get_additional_config(section="results")
        config = get_base_config(section="results")
        config.update(additional_config)
        file_name = config.get("noreference-links")
        file_path = "{0}/{1}_{2}".format(
            config.get("migration-dir"), api.portal.get().getId(), file_name
        )
        with open(file_path, "r") as fp:
            return json.loads(fp.read())

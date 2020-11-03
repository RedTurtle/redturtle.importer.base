# -*- coding: utf-8 -*-
from datetime import datetime
from plone import api
from redturtle.importer.base.interfaces import ISection
from redturtle.importer.base.interfaces import ISectionBlueprint
from redturtle.importer.base.transmogrifier.utils import COUNTKEY
from redturtle.importer.base.transmogrifier.utils import ERROREDKEY
from redturtle.importer.base.transmogrifier.utils import ITEMS_IN
from redturtle.importer.base.transmogrifier.utils import VALIDATIONKEY
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer
from zope.interface import provider

import ast
import base64
import hashlib
import json
import logging
import os
import requests
import six.moves.urllib.request
import six.moves.urllib.parse
import six.moves.urllib.error


logger = logging.getLogger(__name__)


@implementer(ISection)
@provider(ISectionBlueprint)
class CachedCatalogSourceSection(object):
    def __init__(self, transmogrifier, name, options, previous):
        self.debug_infos = {}
        # options.update(additional_config)
        self.previous = previous
        self.options = options
        self.context = transmogrifier.context

        self.remote_url = self.get_option(
            "remote-url", "http://localhost:8080"
        )
        self.remote_username = self.get_option("remote-username", "admin")
        self.remote_password = self.get_option("remote-password", "admin")

        self.default_local_path = self.get_option("default-local-path", "")

        # catalog_path = self.get_option("catalog-path", "/Plone/portal_catalog")
        # self.site_path_length = len("/".join(catalog_path.split("/")[:-1]))
        self.remote_skip_paths = ast.literal_eval(
            self.get_option("remote-skip-paths", "[]")
        )
        self.skip_private = json.loads(
            self.get_option("skip-private", "False").lower()
        )
        self.remote_root = self.get_option("remote-root", "")

        # next is for communication with 'logger' section
        self.annotations = IAnnotations(self.context.REQUEST)
        self.storage = self.annotations.setdefault(VALIDATIONKEY, [])
        self.errored = self.annotations.setdefault(ERROREDKEY, [])
        self.item_count = self.annotations.setdefault(COUNTKEY, {})
        self.items_in = self.annotations.setdefault(ITEMS_IN, {})

        # Forge request
        catalog_query = self.get_option("catalog-query", None)
        self.payload = {}
        if catalog_query:
            catalog_query = " ".join(catalog_query.split())
            catalog_query = base64.b64encode(catalog_query.encode("utf-8"))
            self.payload = {"catalog_query": catalog_query}
        # Make request
        resp = requests.get(
            "{url}{root}/rt_get_catalog_results".format(
                url=self.remote_url, root=self.remote_root
            ),
            params=self.payload,
            auth=(self.remote_username, self.remote_password),
        )
        self.item_paths = resp.json()
        self.item_count["total"] = len(self.item_paths)
        self.item_count["remaining"] = len(self.item_paths)

        # creo tutte le folder dove salvare i file della migrazione
        self.migration_dir = self.get_option("migration-dir", "/tmp/migration")
        if not os.path.exists(self.migration_dir):
            os.makedirs(self.migration_dir)

        # cartella per la cache degli oggetti
        self.cache_dir = self.get_option(
            "cache-dir", "/tmp/migration/migration_cache"
        )
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        self.incremental_migration = options.get("incremental-migration") in (
            "true",
            "True",
            "1",
            True,
            1,
        )
        self.ignore_cache = options.get("ignore-cache") in (
            "true",
            "True",
            "1",
            True,
            1,
        )

    def get_option(self, name, default):
        """Get an option from the request if available and fallback to the
        transmogrifier config.
        """
        request = getattr(self.context, "REQUEST", None)
        if request is not None:
            value = request.form.get(
                "form.widgets." + name.replace("-", "_"),
                self.options.get(name, default),
            )
        else:
            value = self.options.get(name, default)
        # if isinstance(value, unicode):
        #     value = value.encode('utf8')
        return value

    def __iter__(self):
        for item in self.previous:
            yield item
        for path in self.item_paths:
            skip = False
            for skip_path in self.remote_skip_paths:
                if not skip_path.startswith(self.remote_root):
                    skip_path = self.remote_root + skip_path.lstrip("/")
                if path.startswith(skip_path):
                    skip = True

            # Skip old talkback items
            if "talkback" in path:
                skip = True

            if not skip:
                item = self.get_remote_item(path)
                if item:
                    item["_path"] = item["_path"].replace(
                        self.remote_root, self.default_local_path
                    )
                    self.storage.append(item["_path"])

                    yield item
        self.save_debug_in_file()

    def save_debug_in_file(self):
        file_name = self.get_option(
            "file-name-in", "migration_content_in.json"
        )
        file_path = "{0}/{1}_{2}".format(
            self.migration_dir, api.portal.get().getId(), file_name
        )
        with open(file_path, "w") as fp:
            json.dump(self.items_in, fp)

    def slugify(self, path):
        # TODO verificare che non ci siano collisioni
        return hashlib.sha224(path.encode("utf-8")).hexdigest()
        # return base64.urlsafe_b64encode(path)

    def get_local_obj(self, path):
        path = path.replace(self.remote_root, "")
        obj = api.content.get(path=path)
        if not obj:
            logger.info("Item {0} not present locally.".format(path))
            return None
        return obj

    def get_item_from_remote(self, path):
        item_url = "%s%s/get_item" % (
            self.remote_url,
            six.moves.urllib.parse.quote(path),
        )
        resp = requests.get(
            item_url,
            params=self.payload,
            auth=(self.remote_username, self.remote_password),
        )
        if resp.status_code == 404:
            # path has strange chars and encoding encodes it in a wrong way.
            item_url = "%s%s/get_item" % (self.remote_url, path)
            resp = requests.get(
                item_url,
                params=self.payload,
                auth=(self.remote_username, self.remote_password),
            )

        if resp.status_code != 200:
            logger.warning(
                "[SKIPPED] - {url}: {code}".format(
                    url=item_url, code=resp.status_code
                )
            )
            self.items_in[path] = {"path": path, "reason": resp.status_code}
            self.errored.append({"path": path, "reason": resp.status_code})
            return None
        try:
            item = resp.json()
        except Exception:
            logger.warning(
                "[SKIPPED] - {url}: Could not decode json response.".format(
                    url=item_url
                )
            )
            self.items_in[path] = {"path": path, "reason": resp.status_code}
            self.errored.append({"path": path, "reason": resp.status_code})
            return None
        if self.skip_private and item.get("is_private", False):
            logger.warning(
                "[SKIPPED] - {path}: Private item.".format(path=item["_path"])
            )
            info = {
                "id": item.get("_id"),
                "portal_type": item.get("_type"),
                "title": item.get("title"),
                "path": path,
                "reason": "Private item",
            }
            self.items_in[path] = info
            self.errored.append(info)
            return None
        return item

    # TODO: se dal catalogo ci fosse anche lo uid e la data di ultima modifica
    # la cache potrebbe essere ancora più precisa e sarebbe anche possibile
    # una migrazione incrementale, al momento si considera sempre fresh la
    # copia in cache, se c'è.
    def get_remote_item(self, path):
        cachefile = os.path.sep.join(
            [self.cache_dir, self.slugify(path) + ".json"]
        )
        item = self.get_item_from_remote(path)
        if not item:
            return {}

        # incremental migration
        if self.incremental_migration and "relatedItems" not in list(
            item.keys()
        ):
            local_obj = self.get_local_obj(path)
            if local_obj:
                local_object_modification_date = (
                    getattr(local_obj, "modification_date", "")
                    .asdatetime()
                    .replace(second=0, microsecond=0, tzinfo=None)
                )
                remote_object_modification_date = datetime.strptime(
                    item.get("modification_date"), "%Y-%m-%d %H:%M"
                )
                if (
                    local_object_modification_date
                    >= remote_object_modification_date
                ):
                    logger.info(
                        "Preserving destination content, Skipped migration "
                        + "for item {0}".format(path)
                    )
                    return {}
                logger.info(
                    "Content {0} modified after {1}. Importing...".format(
                        path, local_object_modification_date.isoformat()
                    )
                )

        # check element in cache
        if (
            not self.ignore_cache
            and os.path.exists(cachefile)
            and "relatedItems" not in list(item.keys())
        ):
            with open(cachefile, "rb") as json_file:
                try:
                    json_data = json.load(json_file)
                except Exception:
                    #  problems with cache file, skip it
                    json_data = ""
            if json_data:
                try:
                    item_mod_date = datetime.strptime(
                        item.get("modification_date")[:-6],
                        "%Y/%m/%d %H:%M:%S.%f",
                    )
                except ValueError:
                    #  date in different format
                    item_mod_date = datetime.strptime(
                        item.get("modification_date")[:-6], "%Y/%m/%d %H:%M:%S"
                    )
                try:
                    item_cache_mod_date = datetime.strptime(
                        json_data.get("modification_date")[:-6],
                        "%Y/%m/%d %H:%M:%S.%f",
                    )
                except ValueError:
                    # date in different format
                    item_cache_mod_date = datetime.strptime(
                        json_data.get("modification_date")[:-6],
                        "%Y/%m/%d %H:%M:%S",
                    )
                if item_mod_date <= item_cache_mod_date:
                    logger.info("HIT path: {0}".format(path))
                    self.items_in[json_data.get("_uid")] = {
                        "id": json_data.get("_id"),
                        "portal_type": json_data.get("_type"),
                        "title": json_data.get("title"),
                        "path": json_data.get("_path"),
                    }
                    return json_data
                logger.info("MISS path: {0}".format(path))
        if item:
            with open(cachefile, "w", encoding="utf-8") as file:
                json.dump(item, file, indent=2)

        self.items_in[item.get("_uid")] = {
            "id": item.get("_id"),
            "portal_type": item.get("_type"),
            "title": item.get("title"),
            "path": item.get("_path"),
        }

        return item

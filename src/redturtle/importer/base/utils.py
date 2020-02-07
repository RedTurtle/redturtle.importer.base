# -*- coding: utf-8 -*-
from collective.transmogrifier.transmogrifier import configuration_registry
from six.moves.configparser import RawConfigParser

import os


def get_transmogrifier_configuration():
    base_config_path = configuration_registry.getConfiguration(
        "redturtlePlone5Main"
    ).get("configuration")
    parser = RawConfigParser()
    parser.optionxform = str  # case sensitive
    with open(base_config_path) as fp:
        parser.readfp(fp)
    result = {}
    for section in parser.sections():
        result[section] = dict(parser.items(section))

    for section, options in get_additional_config().items():
        result.setdefault(section, {}).update(options)
    return result


def get_additional_config(section="", all=False):
    config = RawConfigParser()
    path = os.environ.get('MIGRATION_FILE_PATH', '')
    if not path:
        path = ".migrationconfig.cfg"
    with open(path) as fp:
        config.readfp(fp)
    result = {}
    for section in config.sections():
        result[section] = dict(config.items(section))
    return result

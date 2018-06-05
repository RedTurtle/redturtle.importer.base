# -*- coding: utf-8 -*-
from collective.transmogrifier.transmogrifier import configuration_registry

import ConfigParser


def get_base_config(section='', all=False):
    base_config_path = configuration_registry.getConfiguration(
        'redturtle.plone5.main').get('configuration')
    config = ConfigParser.ConfigParser()
    config.read(base_config_path)
    if all:
        return get_all_config(config)
    if not config.has_section(section):
        return {}
    return get_config_for_section(config, section)


def get_additional_config(section='', all=False):
    config = ConfigParser.ConfigParser()
    config.read('.migrationconfig.cfg')
    if all:
        return get_all_config(config)
    if not config.has_section(section):
        return {}
    return get_config_for_section(config, section)


def get_all_config(config):
    return [{'id': x, 'config': list(config.items(x))}
            for x in config.sections()]


def get_config_for_section(config, section):
    result = {}
    for k, v in config.items(section):
        result[k] = v
    return result

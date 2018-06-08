# -*- coding: utf-8 -*-
from AccessControl.interfaces import IRoleManager
from Acquisition import aq_base
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import Condition
from collective.transmogrifier.utils import defaultKeys
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import Expression
from collective.transmogrifier.utils import Matcher
from copy import deepcopy
from DateTime import DateTime
from dateutil.parser import parse
from plone.app.discussion.comment import CommentFactory
from plone.app.discussion.interfaces import IConversation
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.uuid.interfaces import IUUID
from ploneorg.migration.interfaces import IDeserializer
from Products.Archetypes.interfaces import IBaseObject
from Products.CMFCore.utils import getToolByName
from redturtle.importer.base import logger
from zope.annotation.interfaces import IAnnotations
from zope.app.container.contained import notifyContainerModified
from zope.interface import classProvides
from zope.interface import implements
from zope.schema import getFieldsInOrder

import base64
import pkg_resources
import pprint

import transaction
import logging

try:
    pkg_resources.get_distribution('plone.app.multilingual')
except pkg_resources.DistributionNotFound:
    HAS_PAM = False
else:
    from plone.app.multilingual.interfaces import ITranslationManager
    HAS_PAM = True

try:
    pkg_resources.get_distribution('cioppino.twothumbs')
except pkg_resources.DistributionNotFound:
    HAS_RATINGS = False
else:
    from cioppino.twothumbs import rate
    HAS_RATINGS = True

VALIDATIONKEY = 'ploneorg.migration.logger'


class PrettyPrinter(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.pprint = pprint.PrettyPrinter().pprint

    def __iter__(self):
        def undict(source):
            """ Recurse through the structure and convert dictionaries
                into sorted lists
            """
            res = list()
            if type(source) is dict:
                source = sorted(source.items())
            if type(source) in (list, tuple):
                for item in source:
                    res.append(undict(item))
            else:
                res = source
            # convert a tuple into tuple back
            if type(source) is tuple:
                res = tuple(res)
            return res

        for item in self.previous:
            self.pprint(undict(item))
            yield item


class DataFields(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.datafield_prefix = options.get('datafield-prefix', '_datafield_')
        self.root_path_length = len(self.context.getPhysicalPath())

    def __iter__(self):
        for item in self.previous:
            # not enough info
            if '_path' not in item:
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item['_path'].lstrip('/')), None)

            # path doesn't exist
            if obj is None:
                yield item
                continue

            # do nothing if we got a wrong object through acquisition
            path = item['_path']
            if path.startswith('/'):
                path = path[1:]
            if '/'.join(obj.getPhysicalPath()[self.root_path_length:]) != path:
                yield item
                continue
            for key in item.keys():

                if not key.startswith(self.datafield_prefix):
                    continue

                fieldname = key[len(self.datafield_prefix):]

                if IBaseObject.providedBy(obj):

                    field = obj.getField(fieldname)
                    if field is None:
                        continue
                    if item[key].has_key('data'):
                        value = base64.b64decode(item[key]['data'])
                    else:
                        value = ''
                    # XXX: handle other data field implementations
                    old_value = field.get(obj).data
                    if value != old_value:
                        field.set(obj, value)
                        obj.setFilename(item[key]['filename'])
                        obj.setContentType(item[key]['content_type'])
                else:
                    # We have a destination DX type
                    field = None
                    for schemata in iterSchemata(obj):
                        for name, s_field in getFieldsInOrder(schemata):
                            if name == fieldname:
                                field = s_field
                                deserializer = IDeserializer(field)
                                value = deserializer(item[key], None, item)
                                field.set(field.interface(obj), value)
                    if not field:
                        print(u'Can\'t find a suitable '
                              u'destination field {0}'.format(fieldname))
            yield item


class WorkflowHistory(object):
    """
    """
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.wftool = getToolByName(self.context, 'portal_workflow')

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'workflowhistory-key' in options:
            workflowhistorykeys = options['workflowhistory-key'].splitlines()
        else:
            workflowhistorykeys = defaultKeys(
                options['blueprint'], name, 'workflow_history')
        self.workflowhistorykey = Matcher(*workflowhistorykeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            workflowhistorykey = self.workflowhistorykey(*item.keys())[0]

            if not pathkey or not workflowhistorykey or \
               workflowhistorykey not in item:  # not enough info
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip('/'), None)
            if obj is None or not getattr(obj, 'workflow_history', False):
                yield item
                continue

            if (IBaseObject.providedBy(obj)
                    or IDexterityContent.providedBy(obj)):
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
                        {current_obj_wf: item_tmp[workflowhistorykey][item_tmp[workflowhistorykey].keys()[0]]})  # noqa
                except Exception:
                    logger.error(u'Failed to copy history to the new'
                                 u' workflow for {0}'.format(
                                     item['_path']))
                    pass
                # In case that we need to change internal state names
                # wf_hist_temp = deepcopy(item[workflowhistorykey])
                # for workflow in wf_hist_temp:
                #     # Normalize workflow
                #     if workflow == u'genweb_review':
                #         for k, workflow2 in enumerate(item_tmp[workflowhistorykey]['genweb_review']):
                #             if 'review_state' in item_tmp[workflowhistorykey]['genweb_review'][k]:
                #                 if item_tmp[workflowhistorykey]['genweb_review'][k]['review_state'] == u'esborrany':
                #                     item_tmp[workflowhistorykey]['genweb_review'][k]['review_state'] = u'visible'
                #
                #         item_tmp[workflowhistorykey]['genweb_simple'] = item_tmp[workflowhistorykey]['genweb_review']
                #         del item_tmp[workflowhistorykey]['genweb_review']

                # get back datetime stamp and set the workflow history
                for workflow in item_tmp[workflowhistorykey]:
                    for k, workflow2 in enumerate(item_tmp[workflowhistorykey][workflow]):
                        if 'time' in item_tmp[workflowhistorykey][workflow][k]:
                            item_tmp[workflowhistorykey][workflow][k]['time'] = DateTime(
                                item_tmp[workflowhistorykey][workflow][k]['time'])

                obj.workflow_history.data = item_tmp[workflowhistorykey]

                # update security
                workflows = self.wftool.getWorkflowsFor(obj)
                if workflows:
                    workflows[0].updateRoleMappingsFor(obj)

            yield item


class LocalRoles(object):
    """ """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'local-roles-key' in options:
            roleskeys = options['local-roles-key'].splitlines()
        else:
            roleskeys = defaultKeys(options['blueprint'], name, 'local_roles')
        self.roleskey = Matcher(*roleskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            roleskey = self.roleskey(*item.keys())[0]

            if not pathkey or not roleskey or \
               roleskey not in item:    # not enough info
                yield item
                continue
            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip('/'), None)
            if obj is None:             # path doesn't exist
                yield item
                continue

            if IRoleManager.providedBy(obj):
                for principal, roles in item[roleskey].items():
                    if roles:
                        obj.manage_addLocalRoles(principal, roles)
                        try:
                            obj.reindexObjectSecurity()
                        except Exception:
                            logger.error(
                                'Failed to reindexObjectSecurity {0}'.format(item['_path']))
            yield item


class LeftOvers(object):
    """ """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'properties-key' in options:
            propertieskeys = options['properties-key'].splitlines()
        else:
            propertieskeys = defaultKeys(
                options['blueprint'], name, 'properties')
        self.propertieskey = Matcher(*propertieskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            propertieskey = self.propertieskey(*item.keys())[0]

            if not pathkey:
                # not enough info
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip('/'), None)

            if obj is None:
                # path doesn't exist
                yield item
                continue

            # Exclude from nav
            if item.get('excludeFromNav', False):
                obj.exclude_from_nav = item.get('excludeFromNav')

            # Open in new window
            if item.get('obrirfinestra', False):
                obj.open_link_in_new_window = item.get('obrirfinestra')
            # Layout and DefaultPage from unicode to str
            if item.get('_layout', False):
                item['_layout'] = str(item['_layout'])
                obj.setLayout(item['_layout'])
            if item.get('_defaultpage', False):
                item['_defaultpage'] = str(item['_defaultpage'])
                # XXX: setDefaultPage si aspetta che la default esista
                # nel folder, se la cartella viene creata prima della
                # default questo non e' possibile, copiata la funzione
                # senza questo controllo da qui:
                # parts/omelette/Products/CMFDynamicViewFTI/browserdefault.py
                # obj.setDefaultPage(item['_defaultpage'])
                try:
                    obj.manage_addProperty(
                        'default_page', item['_defaultpage'], 'string')
                except Exception:
                    pass

                obj.reindexObject(['is_default_page'])

            # Local roles inherit
            if item.get('_local_roles_block', False):
                if item['_local_roles_block']:
                    obj.__ac_local_roles_block__ = True

            # Rebuild CollageAlias AT reference
            if item.get('_type', False):
                if item['_type'] == u'CollageAlias':
                    if item['_atrefs'].get('Collage_aliasedItem', False):
                        try:
                            ref_path = item['language'] + \
                                item['_atrefs']['Collage_aliasedItem'][0][item['_site_path_length']:]
                            ref_obj = self.context.unrestrictedTraverse(
                                str(ref_path))
                            ref_uuid = IUUID(ref_obj)
                            obj.set_target(ref_uuid)
                        except Exception:
                            pass

            # Put creation and modification time on its place
            if item.get('creation_date', False):
                if IDexterityContent.providedBy(item):
                    obj.creation_date = parse(item.get('creation_date'))
                else:
                    obj.creation_date = DateTime(item.get('creation_date'))

            if item.get('modification_date', False):
                if IDexterityContent.providedBy(obj):
                    obj.modification_date = parse(
                        item.get('modification_date'))
                else:
                    obj.creation_date = DateTime(item.get('modification_date'))

            # Set subjects
            if item.get('subject', False):
                obj.setSubject(item['subject'])

            yield item


class Discussions(object):
    """A blueprint for importing comments into plone
    """
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'parent_path')
        self.pathkey = Matcher(*pathkeys)
        if 'comment-type-key' in options:
            comment_type_keys = options['comment-type-key'].splitlines()
        else:
            comment_type_keys = defaultKeys(
                options['blueprint'], name, 'comment_type')
        self.comment_type_key = Matcher(*comment_type_keys)
        self.date_format = options.get('date-format', '%Y/%m/%d %H:%M:%S')

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            typekey = self.comment_type_key(*item.keys())[0]
            # item doesn't exist or the type of comment cannot be
            # created
#            if not pathkey or not typekey:
#                # TODO: log a note
#                yield item
#                continue
            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(
                str(path).lstrip('/'), None)
            # path doesn't exist
            if obj is None:
                yield item
                continue
            discussion = item.get('discussions', [])
            if not discussion:
                yield item
                continue

            id_map = {}
            conversation = IConversation(obj)

            # remove all comments to avoid duplication when override is disabled
            if conversation.items():
                comments_id = [x[0] for x in conversation.items()]
                for value in comments_id:
                    try:
                        del conversation[value]
                    except Exception:
                        print 'WARNING: Discussion with id {0} not found'.format(value)
                        pass

            for comment in discussion:
                new_comment = CommentFactory()

                new_comment.text = comment.get('text')
                new_comment.creator = comment.get('creator')
                new_comment.author_name = comment.get('author_name')
                new_comment.author_username = comment.get('author_username')
                new_comment.author_email = comment.get('author_email')
                new_comment.in_reply_to = id_map.get(
                    comment.get('in_reply_to'), 0)
                new_comment.mime_type = comment.get('mime_type')
                new_comment._owner = comment.get('_owner')
                new_comment.__ac_local_roles__ = comment.get(
                    '__ac_local_roles__')
                new_comment.user_notification = comment.get(
                    'user_notification')
                new_comment.creation_date = DateTime(
                    comment.get('creation_date')).asdatetime()
                new_comment.modification_date = DateTime(
                    comment.get('modification_date')).asdatetime()

                conversation.addComment(new_comment)

                comment_wf = new_comment.workflow_history.data.get('comment_review_workflow')
                if comment_wf:
                    new_comment.workflow_history.data.get('comment_review_workflow')[
                        0]['review_state'] = comment['status']

                id_map.update({comment.get('comment_id')
                              : int(new_comment.comment_id)})

                print('Added comment with id {0} to item {1}'.format(
                    new_comment.comment_id, obj.absolute_url()))
            yield item


class FieldsCorrector(object):
    """ This corrects the differences (mainly in naming) of the incoming fields
        with the expected ones.
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'properties-key' in options:
            propertieskeys = options['properties-key'].splitlines()
        else:
            propertieskeys = defaultKeys(
                options['blueprint'], name, 'properties')
        self.propertieskey = Matcher(*propertieskeys)

    def __iter__(self):

        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            propertieskey = self.propertieskey(*item.keys())[0]

            if not pathkey:
                # not enough info
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                str(item[pathkey]).lstrip('/'), None)

            if obj is None:
                # path doesn't exist
                yield item
                continue

            # Event specific fields
            if item.get('startDate', False):
                item['start'] = item.get('startDate')
            if item.get('endDate', False):
                item['end'] = item.get('endDate')

            # Dublin core
            if item.get('expirationDate', False):
                item['expires'] = item.get('expirationDate')
            if item.get('effectiveDate', False):
                item['effective'] = item.get('effectiveDate')

            yield item


class PAMLinker(object):
    """ Links provided translations using plone.app.multilingual. It assumes
        that the object to be linked objects are already in place, so this
        section is intended to be run on second pass migration phase.
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]

            if HAS_PAM:
                if not pathkey:
                    # not enough info
                    yield item
                    continue

                obj = self.context.unrestrictedTraverse(
                    str(item[pathkey]).lstrip('/'), None)

                if obj is None:
                    # path doesn't exist
                    yield item
                    continue

                if item.get('_translations', False):
                    lang_info = []
                    for lang in item['_translations']:
                        target_obj = self.context.unrestrictedTraverse(
                            str('{0}{1}'.format(lang, item['_translations'][lang])).lstrip('/'), None)
                        if target_obj and (IBaseObject.providedBy(target_obj) or IDexterityContent.providedBy(target_obj)):
                            lang_info.append((target_obj, lang),)
                    try:
                        self.link_translations(lang_info)
                    except IndexError:
                        continue

            yield item

    def link_translations(self, items):
        """
            Links the translations with the declared items with the form:
            [(obj1, lang1), (obj2, lang2), ...] assuming that the first element
            is the 'canonical' (in PAM there is no such thing).
        """
        # Grab the first item object and get its canonical handler
        canonical = ITranslationManager(items[0][0])

        for obj, language in items:
            if not canonical.has_translation(language):
                canonical.register_translation(language, obj)


class OrderSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.every = int(options.get('every', 1000))
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.poskey = defaultMatcher(options, 'pos-key', name, 'gopip')
        # Position of items without a position value
        self.default_pos = int(options.get('default-pos', 1000000))

    def __iter__(self):
        # Store positions in a mapping containing an id to position mapping for
        # each parent path {parent_path: {item_id: item_pos}}.
        positions_mapping = {}
        for item in self.previous:
            keys = item.keys()
            pathkey = self.pathkey(*keys)[0]
            poskey = self.poskey(*keys)[0]

            if not (pathkey and poskey):
                yield item
                continue

            item_id = item[pathkey].split('/')[-1]
            parent_path = '/'.join(item[pathkey].split('/')[:-1])
            if parent_path not in positions_mapping:
                positions_mapping[parent_path] = {}
            positions_mapping[parent_path][item_id] = item[poskey]

            yield item

        # Set positions on every parent
        for path, positions in positions_mapping.items():

            # Normalize positions
            ordered_keys = sorted(positions.keys(), key=lambda x: positions[x])
            normalized_positions = {}
            for pos, key in enumerate(ordered_keys):
                normalized_positions[key] = pos

            # TODO: After the new collective.transmogrifier release (>1.4), the
            # utils.py provides a traverse method.
            from collective.transmogrifier.utils import traverse
            parent = traverse(self.context, path)
            # parent = self.context.unrestrictedTraverse(path.lstrip('/'))
            if not parent:
                continue

            parent_base = aq_base(parent)

            if hasattr(parent_base, 'getOrdering'):
                ordering = parent.getOrdering()
                # Only DefaultOrdering of p.folder is supported
                if (not hasattr(ordering, '_order')
                        and not hasattr(ordering, '_pos')):
                    continue
                order = ordering._order()
                pos = ordering._pos()
                order.sort(key=lambda x: normalized_positions.get(
                    x, pos.get(x, self.default_pos)))
                for i, id_ in enumerate(order):
                    pos[id_] = i

                notifyContainerModified(parent)


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

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        # self.key = Expression(options['key'], transmogrifier, name, options)
        self.template = Expression(options['template'], transmogrifier, name,
                                   options)
        # self.value = Expression(options['value'], transmogrifier, name,
        #                         options)
        self.condition = Condition(options.get('condition', 'python:True'),
                                   transmogrifier, name, options)
        self.previous = previous

        self.available_operators = ['*', '', '=']

        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])

    def __iter__(self):
        for item in self.previous:
            template = unicode(self.template(item))
            result_path = ['', ]
            if self.condition(item, key=template):
                original_path = item['_path'].split('/')
                # Save the original_path in the item
                item['_original_path'] = '/'.join(original_path)
                template = template.split('/')
                if len(original_path) != len(template) and \
                   ('*' not in template or '**' not in template):
                    logger.error(
                        'The template and the length of the path is not the same nad there is no wildcards on it')
                    yield item

                # One to one substitution, no wildcards
                if len(original_path) == len(template) and \
                   u'*' not in template and u'**' not in template:
                    actions = zip(original_path, template)
                    for p_path, operator in actions:
                        if operator not in self.available_operators:
                            # Substitute one string for the other
                            result_path.append(operator)
                        elif operator == '=':
                            result_path.append(p_path)
                        elif operator == '':
                            pass

                # We only attend to the number of partial paths before and after
                # the wildcard
                if u'*' in template or u'**' in template:
                    index = template.index(u'*')
                    # Process the head of the path (until wildcard)
                    head = zip(original_path, template[:index])
                    for p_path, operator in head:
                        if operator not in self.available_operators:
                            # Substitute one string for the other
                            result_path.append(operator)
                        elif operator == '=':
                            result_path.append(p_path)
                        elif operator == '':
                            pass

                    # Need to know how many partial paths we have to copy (*)
                    tail_path_length = len(template[index:]) - 1
                    for p_path in original_path[index:-tail_path_length]:
                        result_path.append(p_path)

                    # Process the tail of the path (from wildcard)
                    original_path_reversed = list(original_path)
                    original_path_reversed.reverse()
                    tail = zip(original_path_reversed,
                               template[-tail_path_length])

                    # Complete the tail
                    for p_path, operator in tail:
                        if operator not in self.available_operators:
                            # Substitute one string for the other
                            result_path.append(operator)
                        elif operator == '=':
                            result_path.append(p_path)
                        elif operator == '':
                            pass

                # Update storage item counter path (for logging)
                if item['_path'] in self.storage:
                    self.storage.remove(item['_path'])
                    self.storage.append('/'.join(result_path))

                # Update item path
                item['_path'] = '/'.join(result_path)

            yield item


class CioppinoTwoThumbsRatings(object):

    """ Migrate ratings from cioppino.twothumbs
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

    def __iter__(self):
        for item in self.previous:
            if item.get('_ratings', False):
                obj = self.context.unrestrictedTraverse(
                    str(item['_path']).lstrip('/'), None)
                if obj is None:
                    # path doesn't exist
                    yield item
                    continue
                yays = 'cioppino.twothumbs.yays'
                nays = 'cioppino.twothumbs.nays'
                rate.setupAnnotations(obj)
                annotations = IAnnotations(obj)
                annotations[yays] = item['_ratings']['ups']
                annotations[nays] = item['_ratings']['downs']

            yield item


class CommitSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.every = int(options.get('every', 1000))
        self.previous = previous

    def __iter__(self):
        count = 0
        for item in self.previous:
            count = (count + 1) % self.every
            if count == 0:
                transaction.savepoint(optimistic=True)
		logging.info('Committing changes!')
                transaction.commit()				
            yield item

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os.path

from cruds_adminlte import utils
from django import template

from django.urls import (reverse, NoReverseMatch)  # django2.0
from django.db import models
from django.utils import six
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()
if hasattr(register, 'assignment_tag'):
    register_tag = register.assignment_tag
else:
    register_tag = register.simple_tag


@register.filter
def get_attr(obj, attr):
    """
    Filter returns obj attribute.
    """
    return getattr(obj, attr)


@register_tag
def crud_url(obj, action, namespace=None):
    try:
        nurl = utils.crud_url_name(type(obj), action)
        if namespace:
            nurl = namespace + ':' + nurl
        if action in utils.LIST_ACTIONS:
            url = reverse(nurl)
        else:
            url = reverse(nurl, kwargs={'pk': obj.pk})
    except NoReverseMatch:
        url = None
    return url


@register_tag
def crud_inline_url(obj, inline, action, namespace=None):

    all_tried_names = []
    try:
        nurl = utils.crud_url_name(type(inline), action, base_model=obj.__class__)
        if namespace:
            nurl = namespace + ':' + nurl
        if action in ['delete', 'update', 'detail']:
            url = reverse(nurl, kwargs={'model_id': obj.pk,
                                        'pk': inline.pk})
        else:
            url = reverse(nurl, kwargs={'model_id': obj.pk})
    except NoReverseMatch as e:
        all_tried_names.append((nurl,e))

        # it could be that base_model is a child class and thus 
        # the url does not exist when the inline was only defined for a
        # parent class
        no_match = True
        for base in obj.__class__.__bases__:
            try:
                nurl = utils.crud_url_name(type(inline), action, base_model=base)
                if namespace:
                    nurl = namespace + ':' + nurl
                if action in ['delete', 'update', 'detail']:
                    url = reverse(nurl, kwargs={'model_id': obj.pk,
                                                'pk': inline.pk})
                else:
                    url = reverse(nurl, kwargs={'model_id': obj.pk})
                no_match = False
            except NoReverseMatch as e:
                all_tried_names.append((nurl,e))

            if not no_match:
                break

        if no_match:
            raise NoReverseMatch('No reverse match was found for any of the following url_names: "'+\
                    '", "'.join(n[0] for n in all_tried_names) +'". These are the raised errors: ' +\
                    ", ".join("{}".format(n[1]) for n in all_tried_names)
                    )

    return url


@register.filter
def format_value(obj, field_name):
    """
    Simple value formatting.

    If value is model instance returns link to update view if exists.
    """

    if '__' in field_name:
        related_model, field_name = field_name.split('__', 1)
        obj = getattr(obj, related_model)

    display_func = getattr(obj, 'get_%s_display' % field_name, None)
    if display_func:
        return display_func()
    value = getattr(obj, field_name)

    if value.__class__.__name__ == 'ManyRelatedManager':
        return format_many_values(obj, field_name)

    if isinstance(value, models.fields.files.FieldFile):
        if value:
            return mark_safe('<a href="%s">%s</a>' % (
                value.url,
                os.path.basename(value.name),
            ))
        else:
            return ''

    if isinstance(value, models.Model):
        #This is a hack to obtain the proper
        #string to find the right url for an object initiated as
        #a child class but referenced as a parent-class object
        #in the CRUD templates.
        try:
            value = value._get_child_object()
        except AttributeError as e:
            pass

        url = crud_url(value, utils.ACTION_UPDATE)
        if url:
            return mark_safe('<a href="%s">%s</a>' % (url, escape(value)))
        else:
            if hasattr(value, 'get_absolute_url'):
                url = getattr(value, 'get_absolute_url')()
                return mark_safe('<a href="%s">%s</a>' % (url, escape(value)))
    if value is None:
        value = ""
    return value


@register.simple_tag
def format_many_values(obj, field_name, separator=', '):
    objects = getattr(obj, field_name).all()
    result = []

    for v in objects:
        #This is a hack to obtain the proper
        #string to find the right url for an object initiated as
        #a child class but referenced as a parent-class object
        #in the CRUD templates.
        try:
            v = v._get_child_object()
        except AttributeError as e:
            pass

        url = crud_url(v, utils.ACTION_UPDATE)
        if url:
            res = mark_safe('<a href="%s">%s</a>' % (url, escape(str(v))))
        elif hasattr(v, 'get_absolute_url'):
            url = getattr(v, 'get_absolute_url')()
            res = mark_safe('<a href="%s">%s</a>' % (url, escape(str(v))))
        else:
            res = escape(str(v))

        result.append(res)

    all_values = mark_safe(separator.join(result))
    return all_values


@register.inclusion_tag('cruds/templatetags/crud_fields.html')
def crud_fields(obj, fields=None):
    """
    Display object fields in table rows::

        <table>
            {% crud_fields object 'id, %}
        </table>

    * ``fields`` fields to include

        If fields is ``None`` all fields will be displayed.
        If fields is ``string`` comma separated field names will be
        displayed.
        if field is dictionary, key should be field name and value
        field verbose name.
    """
    if fields is None:
        fields = utils.get_fields(type(obj))
    elif isinstance(fields, six.string_types):
        field_names = [f.strip() for f in fields.split(',')]
        fields = utils.get_fields(type(obj), include=field_names)

    return {
        'object': obj,
        'fields': fields,
    }


@register_tag
def get_fields(model, fields=None):
    """
    Assigns fields for model.
    """
    include = [f.strip() for f in fields.split(',')] if fields else None
    return utils.get_fields(
        model,
        include
    )

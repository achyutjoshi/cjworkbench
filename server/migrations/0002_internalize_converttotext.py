# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-09 21:02
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    """
    Internalize "converttotext" module.

    Prior to this, users on production used an external module, 'convert-text'.
    Then we introduced number type formats. External modules can't run internal
    code (yet), so we made this module an internal one. But _we had to rename
    it_ because internal modules can't have hyphens in their module names.
    """

    dependencies = [
        ('server', '0001_squashed_0048_auto_20190218_2115'),
    ]

    operations = [
        migrations.RunSQL([
            """
            UPDATE server_wfmodule
            SET module_id_name = 'converttotext'
            WHERE module_id_name = 'convert-text'
            """
        ], elidable=True)
    ]
# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-01-24 23:14
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0039_nix_updatesettingscommands'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='changewfmoduleupdatesettingscommand',
            name='delta_ptr',
        ),
        migrations.RemoveField(
            model_name='changewfmoduleupdatesettingscommand',
            name='wf_module',
        ),
        migrations.DeleteModel(
            name='ChangeWfModuleUpdateSettingsCommand',
        ),
    ]
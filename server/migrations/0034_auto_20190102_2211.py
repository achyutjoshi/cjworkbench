# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-01-02 22:11
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0033_auto_20190102_1723'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='parameterspec',
            name='module_version',
        ),
        migrations.DeleteModel(
            name='ParameterSpec',
        ),
    ]

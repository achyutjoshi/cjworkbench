# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2018-12-13 22:56
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0005_addtabcommand'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='addmodulecommand',
            name='order',
        ),
        migrations.RemoveField(
            model_name='addtabcommand',
            name='position',
        ),
    ]
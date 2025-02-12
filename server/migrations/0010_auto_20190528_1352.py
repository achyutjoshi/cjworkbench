# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-28 13:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0009_auto_20190528_1337'),
    ]

    operations = [
        migrations.AddField(
            model_name='wfmodule',
            name='inprogress_file_upload_id',
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='wfmodule',
            name='inprogress_file_upload_key',
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='wfmodule',
            name='inprogress_file_upload_last_accessed_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]

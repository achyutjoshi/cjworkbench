# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-10-11 16:18
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0130_auto_20181003_1916'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aclentry',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
        ),
        migrations.AlterField(
            model_name='aclentry',
            name='workflow',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acl', to='server.Workflow'),
        ),
    ]

# Generated by Django 5.1.4 on 2025-01-11 10:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('regforma', '0002_lots_author_alter_company_author_alter_lots_country_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lots',
            name='author',
        ),
    ]

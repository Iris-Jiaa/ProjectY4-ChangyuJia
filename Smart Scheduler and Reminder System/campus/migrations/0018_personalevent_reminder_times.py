from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campus', '0017_eventcomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentpersonalevent',
            name='reminder_times',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Comma-separated reminder times for this event, e.g. '60min,15min'. Uses profile default if empty.",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='facultypersonalevent',
            name='reminder_times',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Comma-separated reminder times for this event, e.g. '60min,15min'. Uses profile default if empty.",
                max_length=100,
            ),
        ),
    ]

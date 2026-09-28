"""
Add the Postgres EXCLUDE constraint that makes overlapping scheduled appointments
impossible.

Django cannot express this constraint in the ORM, so it is written as raw SQL. It is the
single most important correctness guarantee in the project: application-level checks give
friendly error messages, but they cannot survive two simultaneous requests. This constraint
can, because the database serialises the check.

Requires the ``btree_gist`` extension (installed in a prior migration).

The tsrange is half-open '[)' so an appointment ending at 14:00 and another starting at
14:00 do NOT conflict -- back-to-back sessions must remain bookable.
"""

from django.db import migrations


CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS btree_gist;"

ADD_EXCLUDE = """
ALTER TABLE booking_appointment
ADD CONSTRAINT appointment_no_overlap
EXCLUDE USING gist (
    tstzrange(start_at, end_at, '[)') WITH &&
)
WHERE (status IN ('scheduled', 'confirmed'));
"""

DROP_EXCLUDE = """
ALTER TABLE booking_appointment
DROP CONSTRAINT IF EXISTS appointment_no_overlap;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_EXTENSION,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=ADD_EXCLUDE,
            reverse_sql=DROP_EXCLUDE,
        ),
    ]

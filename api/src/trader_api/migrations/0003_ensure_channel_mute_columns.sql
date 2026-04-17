ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_notifications_date VARCHAR(10);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_calls_date VARCHAR(10);

-- Safe to backfill notifications from legacy state: runtime already treats a
-- NULL notifications column as fallback to daily_disabled_date.
UPDATE device_registrations
SET daily_disabled_notifications_date = daily_disabled_date
WHERE daily_disabled_notifications_date IS NULL
  AND daily_disabled_date IS NOT NULL;

-- Do not backfill daily_disabled_calls_date from daily_disabled_date.
-- Legacy daily_disabled_date mirrors notifications mute, not calls mute.

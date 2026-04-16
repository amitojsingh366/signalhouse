ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_notifications_date VARCHAR(10);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_calls_date VARCHAR(10);

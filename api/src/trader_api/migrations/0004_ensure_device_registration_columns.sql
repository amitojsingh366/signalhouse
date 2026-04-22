ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS push_token VARCHAR(255);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS platform VARCHAR(10);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS enabled BOOLEAN;

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_date VARCHAR(10);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_notifications_date VARCHAR(10);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_calls_date VARCHAR(10);

ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

UPDATE device_registrations
SET platform = 'ios'
WHERE platform IS NULL OR platform = '';

UPDATE device_registrations
SET enabled = TRUE
WHERE enabled IS NULL;

ALTER TABLE device_registrations
ALTER COLUMN platform SET DEFAULT 'ios';

ALTER TABLE device_registrations
ALTER COLUMN enabled SET DEFAULT TRUE;

ALTER TABLE device_registrations
ALTER COLUMN platform SET NOT NULL;

ALTER TABLE device_registrations
ALTER COLUMN enabled SET NOT NULL;

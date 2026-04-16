ALTER TABLE device_registrations
ADD COLUMN IF NOT EXISTS daily_disabled_notifications_date VARCHAR(10);

-- Preserve legacy mute state so existing devices remain muted for the same day.
UPDATE device_registrations
SET daily_disabled_notifications_date = daily_disabled_date
WHERE daily_disabled_notifications_date IS NULL
  AND daily_disabled_date IS NOT NULL;

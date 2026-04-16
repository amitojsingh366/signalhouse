DO $$
DECLARE
    had_notifications_column BOOLEAN;
    had_calls_column BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'device_registrations'
          AND column_name = 'daily_disabled_notifications_date'
    )
    INTO had_notifications_column;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'device_registrations'
          AND column_name = 'daily_disabled_calls_date'
    )
    INTO had_calls_column;

    ALTER TABLE device_registrations
    ADD COLUMN IF NOT EXISTS daily_disabled_notifications_date VARCHAR(10);

    ALTER TABLE device_registrations
    ADD COLUMN IF NOT EXISTS daily_disabled_calls_date VARCHAR(10);

    -- Backfill only for columns created by this migration to avoid overriding
    -- deliberate per-channel mute preferences in already-migrated environments.
    IF NOT had_notifications_column THEN
        UPDATE device_registrations
        SET daily_disabled_notifications_date = daily_disabled_date
        WHERE daily_disabled_notifications_date IS NULL
          AND daily_disabled_date IS NOT NULL;
    END IF;

    IF NOT had_calls_column THEN
        UPDATE device_registrations
        SET daily_disabled_calls_date = daily_disabled_date
        WHERE daily_disabled_calls_date IS NULL
          AND daily_disabled_date IS NOT NULL;
    END IF;
END $$;

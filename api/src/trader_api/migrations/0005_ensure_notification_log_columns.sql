CREATE TABLE IF NOT EXISTS notification_log (
    id SERIAL PRIMARY KEY,
    device_token VARCHAR(255) NOT NULL,
    notification_type VARCHAR(20) NOT NULL DEFAULT 'signal',
    symbol VARCHAR(20) NOT NULL DEFAULT '',
    signal VARCHAR(4) NOT NULL DEFAULT '',
    strength DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    caller_name VARCHAR(100) NOT NULL DEFAULT '',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    retry_count INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS device_token VARCHAR(255);

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS notification_type VARCHAR(20);

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS symbol VARCHAR(20);

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS signal VARCHAR(4);

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS strength DOUBLE PRECISION;

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS caller_name VARCHAR(100);

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS delivered BOOLEAN;

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS acknowledged BOOLEAN;

ALTER TABLE notification_log
ADD COLUMN IF NOT EXISTS retry_count INTEGER;

UPDATE notification_log
SET notification_type = 'signal'
WHERE notification_type IS NULL;

UPDATE notification_log
SET symbol = ''
WHERE symbol IS NULL;

UPDATE notification_log
SET signal = ''
WHERE signal IS NULL;

UPDATE notification_log
SET strength = 0.0
WHERE strength IS NULL;

UPDATE notification_log
SET caller_name = ''
WHERE caller_name IS NULL;

UPDATE notification_log
SET sent_at = NOW()
WHERE sent_at IS NULL;

UPDATE notification_log
SET delivered = FALSE
WHERE delivered IS NULL;

UPDATE notification_log
SET acknowledged = FALSE
WHERE acknowledged IS NULL;

UPDATE notification_log
SET retry_count = 0
WHERE retry_count IS NULL;

ALTER TABLE notification_log
ALTER COLUMN notification_type SET DEFAULT 'signal';

ALTER TABLE notification_log
ALTER COLUMN symbol SET DEFAULT '';

ALTER TABLE notification_log
ALTER COLUMN signal SET DEFAULT '';

ALTER TABLE notification_log
ALTER COLUMN strength SET DEFAULT 0.0;

ALTER TABLE notification_log
ALTER COLUMN caller_name SET DEFAULT '';

ALTER TABLE notification_log
ALTER COLUMN sent_at SET DEFAULT NOW();

ALTER TABLE notification_log
ALTER COLUMN delivered SET DEFAULT FALSE;

ALTER TABLE notification_log
ALTER COLUMN acknowledged SET DEFAULT FALSE;

ALTER TABLE notification_log
ALTER COLUMN retry_count SET DEFAULT 0;

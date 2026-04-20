ALTER TABLE portfolio_meta
ADD COLUMN IF NOT EXISTS performance_baseline DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- Backfill existing portfolios so percentage calculations remain stable.
UPDATE portfolio_meta
SET performance_baseline = initial_capital
WHERE performance_baseline = 0.0
  AND initial_capital > 0.0;

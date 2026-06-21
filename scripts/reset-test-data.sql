-- Reset bot test data: transactions, wallet balances, referral/discount stats.
-- Does NOT delete users, VPN configs, or panel admin accounts.
-- Run via: ./scripts/reset-test-data.sh

BEGIN;

-- Before counts (shown in shell wrapper)
SELECT 'transactions' AS table_name, COUNT(*) AS rows FROM transactions
UNION ALL SELECT 'users_with_balance', COUNT(*) FROM users WHERE balance <> 0
UNION ALL SELECT 'referrals_with_bonus', COUNT(*) FROM referrals WHERE total_bonus_given <> 0 OR purchase_count <> 0
UNION ALL SELECT 'discount_usage', COUNT(*) FROM discount_usage;

TRUNCATE TABLE transactions RESTART IDENTITY;

UPDATE users SET balance = 0, updated_at = NOW();

UPDATE referrals
SET purchase_count = 0,
    total_bonus_given = 0,
    friend_bonus_given = false;

TRUNCATE TABLE discount_usage RESTART IDENTITY;
UPDATE discount_codes SET used_count = 0;

-- Panel audit log (same DB, optional but keeps reports clean)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
        TRUNCATE TABLE audit_logs RESTART IDENTITY;
    END IF;
END $$;

COMMIT;

SELECT 'done' AS status,
       (SELECT COUNT(*) FROM transactions) AS transactions_left,
       (SELECT COALESCE(SUM(balance), 0) FROM users) AS total_balance_left;

-- Delete Telegram bot users by tg_id so /start registers them as brand-new.
-- Also removes referral rows, configs, transactions, discount usage (via CASCADE).
--
-- Set ids before running, e.g. in psql:
--   \set ids '111111111,222222222,333333333'

BEGIN;

DELETE FROM notification_logs
WHERE user_id = ANY (string_to_array(:'ids', ',')::bigint[]);

DELETE FROM referrals
WHERE referred_id = ANY (string_to_array(:'ids', ',')::bigint[])
   OR referrer_id = ANY (string_to_array(:'ids', ',')::bigint[]);

DELETE FROM users
WHERE tg_id = ANY (string_to_array(:'ids', ',')::bigint[]);

COMMIT;

SELECT 'deleted_users' AS status,
       COUNT(*) AS remaining_matching
FROM users
WHERE tg_id = ANY (string_to_array(:'ids', ',')::bigint[]);

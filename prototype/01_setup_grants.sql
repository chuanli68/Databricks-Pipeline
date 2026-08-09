-- ============================================================
-- Prototype step 1: access control (doc 05, scaled down)
--
-- Free Edition notes:
--  * One metastore, no account console. Account-level groups may not be
--    creatable; this script therefore grants to USERS directly.
--  * To demo isolation for real, invite a second user:
--    Settings → Identity and access → Users → Add user (they sign in
--    with email OTP / Google / Microsoft). Then set the variables below.
--  * With only one user (you = metastore admin, sees everything),
--    isolation is still verifiable: run 02b_access_check.sql which
--    inspects grants rather than relying on your own visibility.
-- ============================================================

-- >>> EDIT THESE two emails before running <<<
-- Public-markets analyst:
--   e.g. 'pubmkt.analyst@gmail.com'
-- Private-markets analyst:
--   e.g. 'pvtmkt.analyst@gmail.com'

-- ---------- Public-markets analyst ----------
GRANT USE CATALOG ON CATALOG pubmkt_gold TO `pubmkt.analyst@gmail.com`;
GRANT USE SCHEMA  ON CATALOG pubmkt_gold TO `pubmkt.analyst@gmail.com`;
GRANT SELECT      ON CATALOG pubmkt_gold TO `pubmkt.analyst@gmail.com`;

-- shared reference data: readable by both orgs
GRANT USE CATALOG ON CATALOG ref_master TO `pubmkt.analyst@gmail.com`;
GRANT USE SCHEMA  ON SCHEMA  ref_master.reference TO `pubmkt.analyst@gmail.com`;
GRANT SELECT      ON SCHEMA  ref_master.reference TO `pubmkt.analyst@gmail.com`;
-- deliberately NOT granted: ref_master.instrument (identity spine is runtime-only)

-- ---------- Private-markets analyst ----------
GRANT USE CATALOG ON CATALOG pvtmkt_gold TO `pvtmkt.analyst@gmail.com`;
GRANT USE SCHEMA  ON CATALOG pvtmkt_gold TO `pvtmkt.analyst@gmail.com`;
GRANT SELECT      ON CATALOG pvtmkt_gold TO `pvtmkt.analyst@gmail.com`;

GRANT USE CATALOG ON CATALOG ref_master TO `pvtmkt.analyst@gmail.com`;
GRANT USE SCHEMA  ON SCHEMA  ref_master.reference TO `pvtmkt.analyst@gmail.com`;
GRANT SELECT      ON SCHEMA  ref_master.reference TO `pvtmkt.analyst@gmail.com`;

-- ---------- What is deliberately absent ----------
-- No grant of pvtmkt_* to the pubmkt analyst, and vice versa: absence of
-- USE CATALOG means the other org's catalogs are invisible AND unqueryable.
-- No grants on *_bronze / *_silver to analysts: consumers read gold only.
-- (In production these grants target groups + service principals; doc 05 §3.)

-- Initialize roles for AVENEL
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'avenel_owner') THEN
    CREATE ROLE avenel_owner WITH LOGIN PASSWORD 'avenel_owner_secret' SUPERUSER;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'avenel_app') THEN
    CREATE ROLE avenel_app WITH LOGIN PASSWORD 'avenel_app_secret' NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;

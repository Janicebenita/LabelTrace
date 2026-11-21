-- Execute as the configured Entra PostgreSQL administrator, from a trusted
-- VNet-connected operator host. Do not put an access token in this file.
-- psql -v app_role='APP-SERVICE-NAME' -v principal_id='APP-MANAGED-IDENTITY-OBJECT-ID' ... -d postgres -f infra/bootstrap-postgres.sql
-- Uses OID-based mapping to avoid directory name lookup privileges.
SELECT * FROM pgaadauth_create_principal_with_oid(:'app_role', :'principal_id', 'service', false, false);
GRANT CONNECT ON DATABASE labeltrace TO :"app_role";
\connect labeltrace
GRANT USAGE, CREATE ON SCHEMA public TO :"app_role";
-- The application owns tables it creates via Alembic. It gets no Entra
-- administration, server creation, or blanket subscription privileges.

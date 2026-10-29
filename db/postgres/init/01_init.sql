-- Base cible PostgreSQL (entrepot de consultation), alimentee par Airbyte depuis rh_source (MySQL).
-- Les tables metier (employes, services, fonctions) ne sont PAS creees ici : c'est Airbyte qui les
-- cree et les maintient (colonnes _airbyte_raw_id / _airbyte_extracted_at / _airbyte_meta comprises),
-- conformement a son mode de fonctionnement standard (Destination V2 / typage-dedoublonnage).
-- Voir scripts/sync_mysql_to_postgres.py pour un repli de developpement qui produit le meme schema.

CREATE SCHEMA IF NOT EXISTS public;

-- Role dedie en lecture seule pour l'API (principe du moindre privilege)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_reader') THEN
    CREATE ROLE api_reader LOGIN PASSWORD 'api_reader_pwd';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE rh_target TO api_reader;
GRANT USAGE ON SCHEMA public TO api_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO api_reader;

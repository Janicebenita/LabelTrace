"""Identity credentials and fresh PostgreSQL tokens, never committed account keys."""
import os
from functools import lru_cache

POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

@lru_cache(maxsize=1)
def credential():
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
    client_id = os.getenv("AZURE_CLIENT_ID")
    if os.getenv("AZURE_AUTH_MODE", "default") == "managed_identity":
        return ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
    return DefaultAzureCredential(managed_identity_client_id=client_id,
                                 exclude_interactive_browser_credential=True)

def postgres_connect_parameters():
    return {"host": os.environ["PGHOST"], "dbname": os.getenv("PGDATABASE", "labeltrace"),
            "user": os.environ["PGUSER"], "port": int(os.getenv("PGPORT", "5432")),
            "sslmode": "verify-full", "sslrootcert":os.getenv("PGSSLROOTCERT","system"), "connect_timeout": 10,
            "password": credential().get_token(POSTGRES_SCOPE).token}

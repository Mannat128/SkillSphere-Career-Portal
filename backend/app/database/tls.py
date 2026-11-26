def database_engine_options(database_ssl_ca):
    """Return shared DBAPI TLS options for application and Alembic engines."""
    if not database_ssl_ca:
        return {"connect_args": {}}
    return {
        "connect_args": {
            "ssl_ca": database_ssl_ca,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }
    }

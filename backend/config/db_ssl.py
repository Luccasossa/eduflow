from pathlib import Path


def resolve_db_ssl_ca(value, base_dir):
    """Return an absolute CA path, using the bundled certificate by default."""
    base_dir = Path(base_dir)
    ca_path = Path(value.strip()) if value and value.strip() else None
    if ca_path is None:
        ca_path = base_dir / "certificados" / "ca (2).pem"
    elif not ca_path.is_absolute():
        ca_path = base_dir / ca_path
    return str(ca_path)

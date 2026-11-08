from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from config.db_ssl import resolve_db_ssl_ca


class DbSslCaSettingsTests(SimpleTestCase):
    def test_empty_value_uses_bundled_certificate_path(self):
        with TemporaryDirectory() as directory:
            expected = Path(directory) / "certificados" / "ca (2).pem"
            self.assertEqual(resolve_db_ssl_ca("", directory), str(expected))

    def test_whitespace_value_uses_bundled_certificate_path(self):
        with TemporaryDirectory() as directory:
            expected = Path(directory) / "certificados" / "ca (2).pem"
            self.assertEqual(resolve_db_ssl_ca("  ", directory), str(expected))

    def test_relative_path_is_resolved_from_backend_base_dir(self):
        with TemporaryDirectory() as directory:
            expected = Path(directory) / "certificados" / "institution.pem"
            self.assertEqual(
                resolve_db_ssl_ca("certificados/institution.pem", directory),
                str(expected),
            )

    def test_absolute_path_is_preserved(self):
        with TemporaryDirectory() as directory:
            expected = Path(directory) / "custom-ca.pem"
            self.assertEqual(resolve_db_ssl_ca(str(expected), "ignored"), str(expected))

    def test_nonexistent_path_is_resolved_but_not_checked_here(self):
        with TemporaryDirectory() as directory:
            expected = Path(directory) / "missing.pem"
            resolved = Path(resolve_db_ssl_ca("missing.pem", directory))
            self.assertEqual(resolved, expected)
            self.assertFalse(resolved.exists())

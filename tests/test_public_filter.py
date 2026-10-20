"""Privacy layers: allowlist selection and the denylist audit that aborts publishing."""

import unittest

import _path  # noqa: F401

from personal_ai_agents.privacy import public_filter as pf


class PublicFilter(unittest.TestCase):
    def test_allowlist_and_refused_category(self):
        habits = [
            {"id": "H01", "category": "study"},
            {"id": "H02", "category": "health"},
            {"id": "H99", "category": "study"},
        ]
        self.assertEqual([h["id"] for h in pf.select(habits)], ["H01"])

    def test_audit_catches_accented_and_uppercase(self):
        self.assertTrue(pf.findings("<p>Consulta MÉDICA amanhã</p>"))

    def test_audit_catches_email_and_cpf(self):
        self.assertTrue(pf.findings("contact: someone@example.com"))
        self.assertTrue(pf.findings("id 123.456.789-00"))

    def test_clean_page_passes(self):
        self.assertEqual(pf.findings("<h1>Study streak: 12 days</h1>"), [])


if __name__ == "__main__":
    unittest.main()

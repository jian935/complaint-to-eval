import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaint_to_eval.redact import has_personal_data, redact  # noqa: E402


class TestRedact(unittest.TestCase):
    def test_common_identifiers_are_replaced(self):
        text = "mail a.li@example.com tel 13800138000 site https://example.com/a @someone"
        clean, counts = redact(text)
        self.assertIn("[EMAIL]", clean)
        self.assertIn("[PHONE_CN]", clean)
        self.assertIn("[URL]", clean)
        self.assertNotIn("a.li@example.com", clean)
        self.assertNotIn("13800138000", clean)
        self.assertNotIn("https://", clean)
        self.assertFalse(has_personal_data(clean))
        self.assertEqual(1, counts["EMAIL"])
        self.assertEqual(1, counts["PHONE_CN"])

    def test_id_card_and_ipv4(self):
        clean, counts = redact("id 11010119900307123X from 192.168.1.20")
        self.assertIn("[ID_CN]", clean)
        self.assertIn("[IPV4]", clean)
        self.assertFalse(has_personal_data(clean))

    def test_plain_feedback_is_unchanged(self):
        text = "回答里直接编造数据，说转化率是 87%。"
        clean, counts = redact(text)
        self.assertEqual(text, clean)
        self.assertEqual({}, counts)

    def test_placeholders_do_not_recurse(self):
        clean, _ = redact("a.li@example.com @someone")
        self.assertEqual("[EMAIL] [HANDLE]", clean)


if __name__ == "__main__":
    unittest.main()

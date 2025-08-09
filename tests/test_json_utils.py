import unittest
from bin.core import parse_llm_json, sanitize_html

class TestJsonUtils(unittest.TestCase):
    def test_parse_llm_json(self):
        txt = "```json\n{\"a\":1}\n```"
        d = parse_llm_json(txt)
        self.assertEqual(d["a"], 1)

    def test_sanitize_html(self):
        dirty = '<script>alert(1)</script><p>ok</p>'
        clean = sanitize_html(dirty)
        self.assertIn("<p>ok</p>", clean)
        self.assertNotIn("<script>", clean)

if __name__ == "__main__":
    unittest.main()

import unittest

from bin.core import GlobalCfg, load_config


class TestConfig(unittest.TestCase):
    def test_load(self):
        cfg = load_config()
        self.assertIsInstance(cfg, GlobalCfg)
        self.assertTrue(cfg.pipeline.video_length_seconds > 0)


if __name__ == "__main__":
    unittest.main()

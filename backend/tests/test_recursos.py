"""AUD6-S12-002: memory guard for the in-process tag worker."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import recursos  # noqa: E402


class RecursosTests(unittest.TestCase):
    def _cgroup(self, files):
        folder = Path(tempfile.mkdtemp())
        for name, value in files.items():
            (folder / name).write_text(value)
        return folder

    def test_cgroup_v2_usage_and_threshold(self):
        folder = self._cgroup({"memory.current": "400\n", "memory.max": "500\n"})
        with patch.object(recursos, "_CGROUP_V2", folder):
            self.assertEqual(recursos.memoria(), {"usada_bytes": 400, "limite_bytes": 500})
            self.assertTrue(recursos.memoria_apertada(0.8))
            self.assertFalse(recursos.memoria_apertada(0.9))

    def test_unlimited_or_missing_values_never_block(self):
        folder = self._cgroup({"memory.current": "400", "memory.max": "max"})
        empty = Path(tempfile.mkdtemp())
        with patch.object(recursos, "_CGROUP_V2", folder), patch.object(recursos, "_CGROUP_V1", empty):
            self.assertEqual(recursos.memoria()["limite_bytes"], None)
            self.assertFalse(recursos.memoria_apertada())
        with patch.object(recursos, "_CGROUP_V2", empty), patch.object(recursos, "_CGROUP_V1", empty):
            self.assertEqual(recursos.memoria(), {"usada_bytes": None, "limite_bytes": None})
            self.assertFalse(recursos.memoria_apertada())

    def test_cgroup_v1_fallback_ignores_unlimited_sentinel(self):
        empty = Path(tempfile.mkdtemp())
        v1 = self._cgroup({"memory.usage_in_bytes": "100", "memory.limit_in_bytes": str(1 << 62)})
        with patch.object(recursos, "_CGROUP_V2", empty), patch.object(recursos, "_CGROUP_V1", v1):
            self.assertEqual(recursos.memoria(), {"usada_bytes": 100, "limite_bytes": None})


if __name__ == "__main__":
    unittest.main()

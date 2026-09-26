import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sidee", ROOT / "sidee.py")
sidee = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sidee)


class BootstrapTests(unittest.TestCase):
    def test_generated_bootstrap_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = sidee._app_context_bootstrap_html("vidaa.smartone-iptv.com")
            path = pathlib.Path(tmp) / "bootstrap.html"
            path.write_text(html, encoding="utf-8")
            self.assertNotIn("runNoopWrite", html)
            self.assertNotIn("fileWrite'", html)
            subprocess.run(["node", "tests/hspdk-context.test.js", str(path)], cwd=ROOT, check=True)
            old_reports, old_sync = sidee.REPORTS_DIR, sidee.queue_report_sync
            try:
                sidee.REPORTS_DIR = pathlib.Path(tmp)
                sidee.queue_report_sync = lambda *args: None
                probe = {"readOnly": True, "status": "NO_FILE_PAIR_OBSERVED"}
                data = {"clientBuildId": sidee.client_build_id(), "legacyHspdkContext": probe}
                report = sidee._save_app_context_bootstrap(data, "vidaa.smartone-iptv.com", "test")
                self.assertEqual(report["legacyHspdkContext"], probe)
                self.assertTrue(report["buildMatch"])
                data["clientBuildId"] = "stale"
                report = sidee._save_app_context_bootstrap(data, "vidaa.smartone-iptv.com", "test")
                self.assertFalse(report["buildMatch"])
                self.assertEqual(report["summary"]["appInfoWrite"], "NOT_RUN")
            finally:
                sidee.REPORTS_DIR, sidee.queue_report_sync = old_reports, old_sync


if __name__ == "__main__":
    unittest.main()

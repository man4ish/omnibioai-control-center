"""tests/test_main.py"""
from __future__ import annotations
import os, subprocess, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import control_center.main as main_module
from control_center.main import _JobState, _workspace_root, app

client = TestClient(app)

def _reset_job():
    j = main_module._job
    with j._lock:
        j.status = "idle"
        j.started_at = None
        j.finished_at = None
        j.message = ""

class TestJobState(unittest.TestCase):
    def _fresh(self): return _JobState()
    def setUp(self): _reset_job()
    def test_initial_idle(self): self.assertEqual(self._fresh().as_dict()["status"], "idle")
    def test_initial_started_at_none(self): self.assertIsNone(self._fresh().as_dict()["started_at"])
    def test_initial_finished_at_none(self): self.assertIsNone(self._fresh().as_dict()["finished_at"])
    def test_initial_message_empty(self): self.assertEqual(self._fresh().as_dict()["message"], "")
    def test_start_sets_running(self):
        j = self._fresh(); j.start()
        self.assertEqual(j.as_dict()["status"], "running")
    def test_start_sets_started_at(self):
        j = self._fresh(); j.start()
        self.assertIsNotNone(j.as_dict()["started_at"])
    def test_start_clears_finished_at(self):
        j = self._fresh(); j.start(); j.finish(); j.start()
        self.assertIsNone(j.as_dict()["finished_at"])
    def test_start_clears_message(self):
        j = self._fresh(); j.fail("old"); j.start()
        self.assertEqual(j.as_dict()["message"], "")
    def test_finish_sets_done(self):
        j = self._fresh(); j.start(); j.finish("x")
        self.assertEqual(j.as_dict()["status"], "done")
    def test_finish_sets_message(self):
        j = self._fresh(); j.start(); j.finish("done msg")
        self.assertEqual(j.as_dict()["message"], "done msg")
    def test_finish_sets_finished_at(self):
        j = self._fresh(); j.start(); j.finish()
        self.assertIsNotNone(j.as_dict()["finished_at"])
    def test_finish_empty_message_ok(self):
        j = self._fresh(); j.start(); j.finish()
        self.assertEqual(j.as_dict()["message"], "")
    def test_fail_sets_error(self):
        j = self._fresh(); j.start(); j.fail("err")
        self.assertEqual(j.as_dict()["status"], "error")
    def test_fail_sets_message(self):
        j = self._fresh(); j.start(); j.fail("FileNotFoundError")
        self.assertIn("FileNotFoundError", j.as_dict()["message"])
    def test_fail_sets_finished_at(self):
        j = self._fresh(); j.start(); j.fail("e")
        self.assertIsNotNone(j.as_dict()["finished_at"])
    def test_as_dict_has_all_keys(self):
        d = self._fresh().as_dict()
        for k in ("status","started_at","finished_at","message"):
            self.assertIn(k, d)
    def test_thread_safety(self):
        j = self._fresh(); errors = []
        def w():
            try: j.start(); time.sleep(0.005); j.finish("ok")
            except Exception as e: errors.append(e)
        ts = [threading.Thread(target=w) for _ in range(10)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(errors, [])

class TestWorkspaceRoot(unittest.TestCase):
    def test_default(self):
        os.environ.pop("WORKSPACE_ROOT", None)
        self.assertEqual(_workspace_root(), Path("/workspace"))
    def test_env_var(self):
        os.environ["WORKSPACE_ROOT"] = "/x"
        try: self.assertEqual(_workspace_root(), Path("/x"))
        finally: del os.environ["WORKSPACE_ROOT"]
    def test_returns_path(self): self.assertIsInstance(_workspace_root(), Path)

class TestDashboard(unittest.TestCase):
    def setUp(self): _reset_job()
    def test_200(self): self.assertEqual(client.get("/").status_code, 200)
    def test_html(self): self.assertIn("text/html", client.get("/").headers["content-type"])
    def test_title(self): self.assertIn("OmniBioAI Control Center", client.get("/").text)
    def test_generate_button(self): self.assertIn("Generate Report", client.get("/").text)
    def test_summary_fetch(self): self.assertIn("/summary", client.get("/").text)
    def test_status_poll(self): self.assertIn("/report/status", client.get("/").text)
    def test_auto_refresh(self): self.assertIn("setInterval", client.get("/").text)
    def test_cards_container(self): self.assertIn('id="cards"', client.get("/").text)
    def test_banner_container(self): self.assertIn('id="banner"', client.get("/").text)
    def test_report_link(self): self.assertIn('href="/report"', client.get("/").text)

class TestReportGenerate(unittest.TestCase):
    def setUp(self): _reset_job()
    def _post(self):
        with patch("control_center.main.threading.Thread") as m:
            m.return_value = MagicMock()
            return client.post("/report/generate"), m
    def test_200_when_idle(self): self.assertEqual(self._post()[0].status_code, 200)
    def test_started_status(self): self.assertEqual(self._post()[0].json()["status"], "started")
    def test_409_when_running(self):
        main_module._job.start()
        self.assertEqual(client.post("/report/generate").status_code, 409)
    def test_409_has_error_key(self):
        main_module._job.start()
        self.assertIn("error", client.post("/report/generate").json())
    def test_job_set_running(self):
        self._post()
        self.assertEqual(main_module._job.as_dict()["status"], "running")
    def test_thread_started(self):
        _, m = self._post()
        m.return_value.start.assert_called_once()
    def test_thread_is_daemon(self):
        with patch("control_center.main.threading.Thread") as m:
            m.return_value = MagicMock()
            client.post("/report/generate")
        self.assertTrue(m.call_args[1].get("daemon", False))

class TestReportStatus(unittest.TestCase):
    def setUp(self): _reset_job()
    def test_200(self): self.assertEqual(client.get("/report/status").status_code, 200)
    def test_has_status(self): self.assertIn("status", client.get("/report/status").json())
    def test_has_report_exists(self): self.assertIn("report_exists", client.get("/report/status").json())
    def test_has_generated_at(self): self.assertIn("report_generated_at", client.get("/report/status").json())
    def test_idle_by_default(self): self.assertEqual(client.get("/report/status").json()["status"], "idle")
    def test_report_exists_false(self):
        os.environ["WORKSPACE_ROOT"] = "/nonexistent"
        try: self.assertFalse(client.get("/report/status").json()["report_exists"])
        finally: del os.environ["WORKSPACE_ROOT"]
    def test_report_generated_at_none(self):
        os.environ["WORKSPACE_ROOT"] = "/nonexistent"
        try: self.assertIsNone(client.get("/report/status").json()["report_generated_at"])
        finally: del os.environ["WORKSPACE_ROOT"]
    def test_report_exists_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"out"/"reports"; p.mkdir(parents=True)
            (p/"omnibioai_ecosystem_report.html").write_text("<html/>")
            os.environ["WORKSPACE_ROOT"] = tmp
            try: self.assertTrue(client.get("/report/status").json()["report_exists"])
            finally: del os.environ["WORKSPACE_ROOT"]
    def test_generated_at_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"out"/"reports"; p.mkdir(parents=True)
            (p/"omnibioai_ecosystem_report.html").write_text("<html/>")
            os.environ["WORKSPACE_ROOT"] = tmp
            try: self.assertIsNotNone(client.get("/report/status").json()["report_generated_at"])
            finally: del os.environ["WORKSPACE_ROOT"]
    def test_reflects_running(self):
        main_module._job.start()
        self.assertEqual(client.get("/report/status").json()["status"], "running")
    def test_reflects_done(self):
        main_module._job.start(); main_module._job.finish("ok")
        self.assertEqual(client.get("/report/status").json()["status"], "done")
    def test_reflects_error(self):
        main_module._job.start(); main_module._job.fail("bad")
        self.assertEqual(client.get("/report/status").json()["status"], "error")
    def test_message_in_response(self):
        main_module._job.start(); main_module._job.fail("Script not found")
        self.assertIn("Script not found", client.get("/report/status").json()["message"])

class TestRunReportJob(unittest.TestCase):
    def setUp(self): _reset_job(); main_module._job.start()
    def test_fails_script_not_found(self):
        os.environ["WORKSPACE_ROOT"] = "/nonexistent"
        try:
            main_module._run_report_job()
            self.assertEqual(main_module._job.as_dict()["status"], "error")
            self.assertIn("not found", main_module._job.as_dict()["message"])
        finally: del os.environ["WORKSPACE_ROOT"]
    def test_succeeds_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
            (d/"generate_report.py").write_text('print("done")')
            os.environ["WORKSPACE_ROOT"] = tmp
            try: main_module._run_report_job(); self.assertEqual(main_module._job.as_dict()["status"], "done")
            finally: del os.environ["WORKSPACE_ROOT"]
    def test_last_stdout_line_as_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
            (d/"generate_report.py").write_text('print("line1")\nprint("✓ Report written")')
            os.environ["WORKSPACE_ROOT"] = tmp
            try: main_module._run_report_job(); self.assertIn("✓ Report written", main_module._job.as_dict()["message"])
            finally: del os.environ["WORKSPACE_ROOT"]
    def test_fails_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
            (d/"generate_report.py").write_text('import sys; sys.exit(1)')
            os.environ["WORKSPACE_ROOT"] = tmp
            try: main_module._run_report_job(); self.assertEqual(main_module._job.as_dict()["status"], "error")
            finally: del os.environ["WORKSPACE_ROOT"]
    def test_stderr_as_error_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
            (d/"generate_report.py").write_text('import sys; sys.stderr.write("cloc not found"); sys.exit(1)')
            os.environ["WORKSPACE_ROOT"] = tmp
            try: main_module._run_report_job(); self.assertIn("cloc not found", main_module._job.as_dict()["message"])
            finally: del os.environ["WORKSPACE_ROOT"]
    def test_timeout_sets_error(self):
        with patch("control_center.main.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="p", timeout=600)):
            with tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
                (d/"generate_report.py").write_text("pass")
                os.environ["WORKSPACE_ROOT"] = tmp
                try: main_module._run_report_job(); self.assertIn("timed out", main_module._job.as_dict()["message"])
                finally: del os.environ["WORKSPACE_ROOT"]
    def test_oserror_sets_error(self):
        with patch("control_center.main.subprocess.run", side_effect=OSError("disk full")):
            with tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
                (d/"generate_report.py").write_text("pass")
                os.environ["WORKSPACE_ROOT"] = tmp
                try: main_module._run_report_job(); self.assertIn("disk full", main_module._job.as_dict()["message"])
                finally: del os.environ["WORKSPACE_ROOT"]
    def test_done_message_generic_when_no_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)/"omnibioai-control-center"/"scripts"; d.mkdir(parents=True)
            (d/"generate_report.py").write_text("")
            os.environ["WORKSPACE_ROOT"] = tmp
            try: main_module._run_report_job(); self.assertEqual(main_module._job.as_dict()["message"], "Done")
            finally: del os.environ["WORKSPACE_ROOT"]

if __name__ == "__main__":
    unittest.main()

"""
tests/test_checks.py

Unit tests for:
  - control_center.checks.tcp
  - control_center.checks.http
  - control_center.checks.disk
  - control_center.api.routes_health
  - control_center.api.routes_report
"""

from __future__ import annotations

import os
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from control_center.checks.disk import run_disk_checks
from control_center.checks.http import check_http
from control_center.checks.tcp import check_tcp
from control_center.core.settings import Settings
from control_center.main import app

client = TestClient(app)


# ==============================================================================
# TCP checks
# ==============================================================================

class TestCheckTcp(unittest.TestCase):

    def _open_server(self) -> tuple[socket.socket, int]:
        """Open a listening TCP socket on an ephemeral port."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        return srv, srv.getsockname()[1]

    def test_up_when_port_open(self) -> None:
        srv, port = self._open_server()
        try:
            result = check_tcp("test-svc", "127.0.0.1", port, "tcp")
        finally:
            srv.close()
        self.assertEqual(result["status"], "UP")
        self.assertEqual(result["name"], "test-svc")
        self.assertEqual(result["type"], "tcp")
        self.assertIsInstance(result["latency_ms"], int)
        self.assertGreaterEqual(result["latency_ms"], 0)

    def test_down_when_port_closed(self) -> None:
        result = check_tcp("closed-svc", "127.0.0.1", 19999, "mysql")
        self.assertEqual(result["status"], "DOWN")
        self.assertIn("latency_ms", result)

    def test_down_when_host_missing(self) -> None:
        result = check_tcp("no-host", None, 3306, "mysql")
        self.assertEqual(result["status"], "DOWN")
        self.assertIsNone(result["latency_ms"])
        self.assertIn("Missing host", result["message"])

    def test_target_format(self) -> None:
        result = check_tcp("svc", "127.0.0.1", 9999, "redis")
        self.assertEqual(result["target"], "127.0.0.1:9999")

    def test_kind_preserved(self) -> None:
        result = check_tcp("svc", "127.0.0.1", 9999, "redis")
        self.assertEqual(result["type"], "redis")


# ==============================================================================
# HTTP checks
# ==============================================================================

class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: object) -> None:
        pass


class _ErrorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(503)
        self.end_headers()
        self.wfile.write(b"error")

    def log_message(self, *args: object) -> None:
        pass


def _start_http_server(handler_cls: type) -> tuple[HTTPServer, int]:
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


class TestCheckHttp(unittest.TestCase):

    def test_up_on_200(self) -> None:
        server, port = _start_http_server(_OkHandler)
        try:
            result = check_http("web-svc", {"url": f"http://127.0.0.1:{port}/health"})
        finally:
            server.shutdown()
        self.assertEqual(result["status"], "UP")
        self.assertEqual(result["name"], "web-svc")
        self.assertEqual(result["type"], "http")
        self.assertIsInstance(result["latency_ms"], int)

    def test_down_on_5xx(self) -> None:
        # urllib raises HTTPError for 5xx — check_http catches it and returns DOWN
        server, port = _start_http_server(_ErrorHandler)
        try:
            result = check_http("bad-svc", {"url": f"http://127.0.0.1:{port}/"})
        finally:
            server.shutdown()
        self.assertEqual(result["status"], "DOWN")
        self.assertIn("503", result["message"])

    def test_down_when_unreachable(self) -> None:
        result = check_http(
            "offline", {"url": "http://127.0.0.1:19998/health", "timeout_s": 1}
        )
        self.assertEqual(result["status"], "DOWN")
        self.assertIn("latency_ms", result)

    def test_down_when_url_missing(self) -> None:
        result = check_http("no-url", {})
        self.assertEqual(result["status"], "DOWN")
        self.assertIn("Missing 'url'", result["message"])

    def test_target_is_url(self) -> None:
        url = "http://127.0.0.1:19998/health"
        result = check_http("svc", {"url": url, "timeout_s": 1})
        self.assertEqual(result["target"], url)


# ==============================================================================
# Disk checks
# ==============================================================================

def _make_settings(disk_cfgs: list[dict]) -> Settings:
    return Settings(services={}, system={"disk_checks": disk_cfgs})


class TestDiskChecks(unittest.TestCase):

    def test_up_on_healthy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings([{"path": tmp, "warn_pct_free_below": 0}])
            results = run_disk_checks(settings)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "UP")
        self.assertEqual(results[0]["type"], "disk")

    def test_warn_when_threshold_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Threshold of 100% means always warn
            settings = _make_settings([{"path": tmp, "warn_pct_free_below": 100}])
            results = run_disk_checks(settings)
        self.assertEqual(results[0]["status"], "WARN")
        self.assertIn("Low disk", results[0]["message"])

    def test_warn_on_missing_path(self) -> None:
        settings = _make_settings(
            [{"path": "/nonexistent/path/xyz", "warn_pct_free_below": 10}]
        )
        results = run_disk_checks(settings)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "WARN")

    def test_empty_disk_checks(self) -> None:
        settings = _make_settings([])
        results = run_disk_checks(settings)
        self.assertEqual(results, [])

    def test_no_path_key_skipped(self) -> None:
        settings = _make_settings([{"warn_pct_free_below": 10}])
        results = run_disk_checks(settings)
        self.assertEqual(results, [])

    def test_multiple_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                settings = _make_settings([
                    {"path": tmp1, "warn_pct_free_below": 0},
                    {"path": tmp2, "warn_pct_free_below": 0},
                ])
                results = run_disk_checks(settings)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "UP" for r in results))

    def test_name_includes_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _make_settings([{"path": tmp, "warn_pct_free_below": 0}])
            results = run_disk_checks(settings)
        self.assertIn(tmp, results[0]["name"])


# ==============================================================================
# API routes — GET /health
# ==============================================================================

class TestRoutesHealth(unittest.TestCase):

    def test_health_returns_200(self) -> None:
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_returns_ok_status(self) -> None:
        response = client.get("/health")
        self.assertEqual(response.json()["status"], "ok")

    def test_health_content_type_is_json(self) -> None:
        response = client.get("/health")
        self.assertIn("application/json", response.headers["content-type"])


# ==============================================================================
# API routes — GET /report
# ==============================================================================

class TestRoutesReport(unittest.TestCase):

    def test_report_returns_200(self) -> None:
        response = client.get("/report")
        self.assertEqual(response.status_code, 200)

    def test_report_returns_html(self) -> None:
        response = client.get("/report")
        self.assertIn("text/html", response.headers["content-type"])

    def test_report_shows_placeholder_when_no_file(self) -> None:
        os.environ["WORKSPACE_ROOT"] = "/nonexistent/workspace"
        try:
            response = client.get("/report")
            self.assertIn("not yet generated", response.text)
        finally:
            del os.environ["WORKSPACE_ROOT"]

    def test_report_placeholder_contains_generate_command(self) -> None:
        os.environ["WORKSPACE_ROOT"] = "/nonexistent/workspace"
        try:
            response = client.get("/report")
            self.assertIn("generate_report.py", response.text)
        finally:
            del os.environ["WORKSPACE_ROOT"]

    def test_report_serves_file_when_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "out" / "reports"
            report_dir.mkdir(parents=True)
            report_file = report_dir / "omnibioai_ecosystem_report.html"
            report_file.write_text("<html><body>Test Report</body></html>")
            os.environ["WORKSPACE_ROOT"] = tmp
            try:
                response = client.get("/report")
                self.assertIn("Test Report", response.text)
            finally:
                del os.environ["WORKSPACE_ROOT"]

    def test_report_file_content_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "out" / "reports"
            report_dir.mkdir(parents=True)
            content = "<html><body><h1>OmniBioAI Report</h1></body></html>"
            (report_dir / "omnibioai_ecosystem_report.html").write_text(content)
            os.environ["WORKSPACE_ROOT"] = tmp
            try:
                response = client.get("/report")
                self.assertEqual(response.text, content)
            finally:
                del os.environ["WORKSPACE_ROOT"]


if __name__ == "__main__":
    unittest.main()
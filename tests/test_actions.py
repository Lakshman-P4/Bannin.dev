"""Tests for action endpoints -- kill process, recommendations, disk cleanup."""

import os
import pytest


class TestKillPrepare:
    def test_prepare_kill_invalid_pid(self, client):
        r = client.post("/processes/999999999/kill/prepare")
        assert r.status_code == 404

    def test_prepare_kill_returns_token(self, client):
        """Prepare kill for current process (we won't actually kill it)."""
        pid = os.getpid()
        r = client.post(f"/processes/{pid}/kill/prepare")
        assert r.status_code == 200
        data = r.json()
        assert "confirm_token" in data
        assert data["pid"] == pid

    def test_kill_without_valid_token(self, client):
        pid = os.getpid()
        r = client.post(f"/processes/{pid}/kill", json={"confirm_token": "invalid"})
        assert r.status_code == 400
        assert "error" in r.json()


class TestChildProcesses:
    def test_children_of_current_process(self, client):
        pid = os.getpid()
        r = client.get(f"/processes/{pid}/children")
        assert r.status_code == 200
        data = r.json()
        assert "children" in data
        assert "count" in data
        assert data["pid"] == pid

    def test_children_of_invalid_pid(self, client):
        r = client.get("/processes/999999999/children")
        assert r.status_code == 200
        assert r.json()["count"] == 0


class TestActionPrepare:
    def test_prepare_valid_action(self, client):
        r = client.post("/actions/prepare?action=kill_group&target=Chrome")
        assert r.status_code == 200
        data = r.json()
        assert "confirm_token" in data

    def test_prepare_invalid_action(self, client):
        r = client.post("/actions/prepare?action=format_disk&target=C:")
        assert r.status_code == 400

    def test_dismiss_requires_valid_token(self, client):
        # Prepare a dismiss token first
        r = client.post("/actions/prepare", params={"action": "dismiss", "target": ""})
        assert r.status_code == 200
        token = r.json()["confirm_token"]

        # Execute with valid token
        r = client.post("/actions/execute", json={
            "action": "dismiss",
            "target": "",
            "confirm_token": token,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_dismiss_rejects_invalid_token(self, client):
        r = client.post("/actions/execute", json={
            "action": "dismiss",
            "target": "",
            "confirm_token": "invalid",
        })
        assert r.status_code == 400

    def test_execute_invalid_token(self, client):
        r = client.post("/actions/execute", json={
            "action": "kill_group",
            "target": "Chrome",
            "confirm_token": "invalid",
        })
        assert r.status_code == 400


class TestDiskCleanup:
    def test_disk_cleanup_scan(self, client):
        r = client.get("/disk/cleanup")
        assert r.status_code == 200
        data = r.json()
        assert "targets" in data
        assert "total_reclaimable_bytes" in data
        assert "total_reclaimable_display" in data
        assert "scan_time_seconds" in data

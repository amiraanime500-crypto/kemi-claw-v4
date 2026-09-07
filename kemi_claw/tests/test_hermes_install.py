"""Offline installer guard tests; no downloads, pip installs, or model calls."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install_hermes.sh"
COMMIT = "29112bef099274229cadff79cdff7bf7b99c4b77"
REPO = "https://github.com/NousResearch/hermes-agent.git"


class TestHermesInstallerGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hermes-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.install = self.home / "external hermes"
        self.commands = self.root / "commands"
        self.commands.mkdir()
        self.git_log = self.root / "git.jsonl"
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.commands) + os.pathsep + os.defpath,
            "HERMES_PYTHON": sys.executable,
            "HERMES_INSTALL_DIR": str(self.install),
            "HERMES_HOME": str(self.home / "hermes data"),
            "MOCK_GIT_LOG": str(self.git_log),
            "MOCK_GIT_COMMIT": COMMIT,
            "MOCK_GIT_REMOTE": REPO,
        }
        # Do not use the real git, even if a guard regresses: every command is
        # logged and unknown operations fail closed instead of reaching GitHub.
        git = self.commands / "git"
        git.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['MOCK_GIT_LOG'], 'a', encoding='utf-8') as f:\n"
            "    f.write(json.dumps(args) + '\\n')\n"
            "if args[0] == 'clone':\n"
            "    (pathlib.Path(args[-1]) / '.git').mkdir(parents=True)\n"
            "elif args[0] == '-C':\n"
            "    command = args[2:]\n"
            "    if command == ['remote', 'get-url', 'origin']:\n"
            "        print(os.environ['MOCK_GIT_REMOTE'])\n"
            "    elif command == ['rev-parse', 'HEAD']:\n"
            "        print(os.environ['MOCK_GIT_COMMIT'])\n"
            "    elif command == ['diff', '--quiet', 'HEAD', '--']:\n"
            "        sys.exit(int(os.environ.get('MOCK_GIT_DIRTY', '0')))\n"
            "    else:\n"
            "        sys.exit(99)\n"
            "else:\n"
            "    sys.exit(99)\n",
            encoding="utf-8",
        )
        git.chmod(0o700)

    def run_installer(self, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=self.home,
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def checkout(self):
        (self.install / ".git").mkdir(parents=True)
        self.sentinel = self.install / "user-notes.txt"
        self.sentinel.write_text("keep this", encoding="utf-8")

    def assert_refused(self, result, message):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertFalse((self.home / ".local" / "bin" / "hermes").exists())

    def test_help_does_not_create_an_installation(self):
        result = self.run_installer("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HERMES_PYTHON", result.stdout)
        self.assertFalse(self.install.exists())
        self.assertFalse(self.git_log.exists())

    def test_invalid_arguments_are_rejected_without_side_effects(self):
        for args in [("--unknown",), ("--help", "unexpected"), ("",)]:
            with self.subTest(args=args):
                self.assert_refused(self.run_installer(*args), "Use --help")
        self.assertFalse(self.install.exists())
        self.assertFalse(self.git_log.exists())

    def test_unsupported_python_is_rejected_before_git(self):
        python = self.commands / "unsupported-python"
        python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        python.chmod(0o700)
        self.env["HERMES_PYTHON"] = str(python)
        self.assert_refused(self.run_installer(), "requires Python 3.11")
        self.assertFalse(self.git_log.exists())

    def test_unrelated_directory_is_preserved(self):
        self.install.mkdir()
        sentinel = self.install / "user-data"
        sentinel.write_text("untouched", encoding="utf-8")
        self.assert_refused(self.run_installer(), "not a Hermes checkout")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "untouched")
        self.assertFalse(self.git_log.exists())

    def test_wrong_remote_is_preserved(self):
        self.checkout()
        self.env["MOCK_GIT_REMOTE"] = "https://example.invalid/unrelated.git"
        self.assert_refused(self.run_installer(), "different repository")
        self.assertEqual(self.sentinel.read_text(encoding="utf-8"), "keep this")
        self.assertFalse((self.install / "venv").exists())

    def test_different_release_is_not_downgraded(self):
        self.checkout()
        self.env["MOCK_GIT_COMMIT"] = "a" * 40
        self.assert_refused(self.run_installer(), "Existing Hermes version differs")
        self.assertEqual(self.sentinel.read_text(encoding="utf-8"), "keep this")
        self.assertFalse((self.install / "venv").exists())

    def test_modified_tracked_files_are_preserved(self):
        self.checkout()
        self.env["MOCK_GIT_DIRTY"] = "1"
        self.assert_refused(self.run_installer(), "modified tracked files")
        self.assertEqual(self.sentinel.read_text(encoding="utf-8"), "keep this")
        self.assertFalse((self.install / "venv").exists())

    def test_moved_release_tag_cannot_execute_downloaded_code(self):
        self.env["MOCK_GIT_COMMIT"] = "b" * 40
        self.assert_refused(self.run_installer(), "Release commit verification failed")
        calls = [json.loads(line) for line in self.git_log.read_text().splitlines()]
        self.assertEqual(
            calls[0],
            ["clone", "--depth", "1", "--single-branch", "--branch", "v2026.8.31", REPO, str(self.install)],
        )
        self.assertFalse((self.install / "venv").exists())

    def test_symlinked_venv_is_not_modified(self):
        self.checkout()
        other = self.home / "another projects venv"
        other.mkdir()
        (self.install / "venv").symlink_to(other, target_is_directory=True)
        self.assert_refused(self.run_installer(), "symlinked virtual environment")
        self.assertEqual(list(other.iterdir()), [])

    def test_incomplete_venv_is_not_deleted(self):
        self.checkout()
        venv = self.install / "venv"
        venv.mkdir()
        sentinel = venv / "keep-me"
        sentinel.touch()
        self.assert_refused(self.run_installer(), "Incomplete virtual environment")
        self.assertTrue(sentinel.exists())

    def test_system_python_cannot_be_used_as_a_fake_venv(self):
        self.checkout()
        bin_dir = self.install / "venv" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").symlink_to(sys.executable)
        self.assert_refused(self.run_installer(), "Virtual environment validation failed")
        self.assertEqual(self.sentinel.read_text(encoding="utf-8"), "keep this")


if __name__ == "__main__":
    unittest.main()

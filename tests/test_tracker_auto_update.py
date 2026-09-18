"""The cycle refresh is best-effort and never stages or commits."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.tracker import auto_update


class TestAutoUpdate(unittest.TestCase):
    def test_project_with_ledgers_calls_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with patch.object(auto_update.ledger, "find", return_value=[project / "docs/proposals/19-x.json"]), \
                 patch.object(auto_update.board, "main", return_value=0) as render:
                self.assertTrue(auto_update.update(project))
            render.assert_called_once_with(["--project", str(project)])

    def test_non_project_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(auto_update.ledger, "find", return_value=[]), \
             patch.object(auto_update.board, "main") as render:
            self.assertFalse(auto_update.update(Path(tmp)))
            render.assert_not_called()

    def test_board_failure_does_not_escape_the_hook(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(auto_update.ledger, "find", return_value=[Path(tmp) / "ledger.json"]), \
             patch.object(auto_update.board, "main", return_value=1):
            self.assertFalse(auto_update.update(Path(tmp)))


if __name__ == "__main__":
    unittest.main()

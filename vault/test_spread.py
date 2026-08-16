#!/usr/bin/env python3
"""test_spread.py — TDD RED for the Failure-Spread Orchestrator (AGI design).
Failed tests spread across bricks: bandit picks top-k by capability + solve
rate, each brick declares ONE attack workspace (pair protocol), parallel
hypotheses, first verified fix -> pair-DA hostile review -> merge. Winner
gets solver credit; losers get exploration credit."""
import json, os, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from spread import SpreadOrchestrator

class TestSpread(unittest.TestCase):
    def setUp(self):
        os.environ["SPREAD_ADMIN_KEY"] = "ADMIN"
        self.dir = tempfile.mkdtemp()
        self.s = SpreadOrchestrator(self.dir)

    def tearDown(self):
        os.environ.pop("SPREAD_ADMIN_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_failure_broadcast_selects_solvers(self):
        """A failing test selects top-k bricks by capability match."""
        self.s.register("brick-web", ["build", "browser"])
        self.s.register("brick-sec", ["security", "audit"])
        self.s.register("brick-ml", ["model", "train"])
        solvers = self.s.spread("build failure in browser-dist", k=2)
        self.assertIn("brick-web", solvers)  # capability match
        self.assertEqual(len(solvers), 2)

    def test_pair_protocol_single_owner(self):
        """Each solver declares ONE workspace; no double ownership."""
        self.s.register("brick-web", ["build"])
        self.s.register("brick-sec", ["build"])
        self.s.spread("build failure", k=2)
        ws = self.s.workspaces()
        owners = [w["owner"] for w in ws.values()]
        self.assertEqual(len(owners), len(set(owners)))  # no duplicates

    def test_first_verified_fix_wins(self):
        """First brick to verify a fix is recorded as the winner."""
        self.s.register("brick-web", ["build"])
        self.s.spread("build failure", k=1)
        self.s.verify_fix("brick-web", "failure-1", passed=True)
        self.assertEqual(self.s.winner("failure-1"), "brick-web")

    def test_pair_da_required_before_merge(self):
        """A fix cannot merge without a hostile non-earner DA review."""
        self.s.register_da("security-001", "DA-KEY", admin_key="ADMIN")
        self.s.register("brick-web", ["build"])
        self.s.spread("build failure", k=1)
        self.s.verify_fix("brick-web", "failure-1", passed=True)
        with self.assertRaises(RuntimeError):
            self.s.merge("failure-1")  # DA not yet approved
        self.s.da_approve("failure-1", reviewer="security-001", da_key="DA-KEY")
        self.s.merge("failure-1")  # now allowed

    def test_da_approval_not_forgeable(self):
        """BLOCKER #2 fix: a caller without the DA key cannot forge approval."""
        self.s.register_da("security-001", "DA-KEY", admin_key="ADMIN")
        self.s.register("brick-web", ["build"])
        self.s.spread("build failure", k=1)
        self.s.verify_fix("brick-web", "failure-1", passed=True)
        with self.assertRaises(PermissionError):
            self.s.da_approve("failure-1", reviewer="security-001")  # no da_key
        with self.assertRaises(PermissionError):
            self.s.da_approve("failure-1", reviewer="security-001", da_key="WRONG")
        # legit DA with the key approves
        self.s.da_approve("failure-1", reviewer="security-001", da_key="DA-KEY")
        self.s.merge("failure-1")

    def test_losers_get_exploration_credit(self):
        """Non-winners get exploration credit feeding router priors."""
        self.s.register("brick-web", ["build"])
        self.s.register("brick-sec", ["build"])
        solvers = self.s.spread("build failure", k=2)
        self.s.verify_fix(solvers[0], "failure-1", passed=True)
        self.s.exploration_credit(solvers[1], "failure-1")
        self.assertEqual(self.s.exploration(solvers[1]), 1)

    def test_winner_solver_credit(self):
        """Winner gets solver credit, not exploration credit."""
        self.s.register("brick-web", ["build"])
        self.s.spread("build failure", k=1)
        self.s.verify_fix("brick-web", "failure-1", passed=True)
        self.assertEqual(self.s.solver_credit("brick-web"), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)

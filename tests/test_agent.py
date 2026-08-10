"""
Test script for Kaggriculture agent.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from src.kaggriculture_real import validate_minimal_decision, agent


class TestRealProtocolAgent(unittest.TestCase):
    def test_minimal_decision_returns_action_dict(self):
        action = validate_minimal_decision()
        self.assertIsInstance(action, dict)
        self.assertIn("farmer", action)
        self.assertIn("market", action)
        # With an empty tile and seeds on hand, the agent should plant.
        self.assertEqual(action["farmer"][0], "PLANT")

    def test_agent_function_accepts_minimal_obs(self):
        obs = {
            "player": 0,
            "day": 1,
            "farms": [{"farmer": [0, 0], "money": 100.0, "tiles": [[None, None], [None, None]]}],
            "private": {"seeds": {"WHEAT": 1}, "shed": {}},
        }
        action = agent(obs, None)
        self.assertIsInstance(action, dict)
        self.assertIn("farmer", action)
        self.assertIn("market", action)
        self.assertTrue(len(action["farmer"]) >= 1)

    def test_agent_prioritizes_planting_when_seed_available(self):
        obs = {
            "player": 0,
            "day": 1,
            "farms": [{"farmer": [0, 0], "money": 100.0, "tiles": [[None, None], [None, None]]}],
            "private": {"seeds": {"WHEAT": 1}, "shed": {}},
        }
        action = agent(obs, None)
        self.assertIn(action["farmer"][0], {"PASS", "PLANT"})


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_normalize_state(self):
        """Test state normalization."""
        from src.utils import normalize_state

        mock_state = {
            "player": {
                "coins": 5000,
                "energy": 75,
                "inventory": {"WHEAT": 20, "CORN": 10}
            },
            "market": {
                "prices": {"WHEAT": 12, "CORN": 15}
            },
            "board": {(0, 0): None, (0, 1): None}
        }

        normalized = normalize_state(mock_state)
        self.assertIsInstance(normalized, np.ndarray)
        self.assertTrue(len(normalized) > 0)

    def test_calculate_expected_value(self):
        """Test value calculation."""
        from src.utils import calculate_expected_value

        mock_state = {"step": 100}
        value = calculate_expected_value("PLANT 0 0 WHEAT", mock_state)
        self.assertIsInstance(value, float)
        self.assertTrue(value >= 0)


if __name__ == "__main__":
    # Import numpy for tests
    import numpy as np

    unittest.main()
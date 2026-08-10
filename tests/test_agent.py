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

    def test_agent_prefers_profitable_crop(self):
        obs = {
            "player": 0,
            "day": 1,
            "farms": [{"farmer": [0, 0], "money": 100.0, "tiles": [[None, None], [None, None]]}],
            "private": {"seeds": {}, "shed": {}},
            "prices": {"CORN": 26.0, "WHEAT": 15.0},
            "seed_costs": {"CORN": 15.0, "WHEAT": 10.0}
        }
        action = agent(obs, None)

        # It should buy CORN because it's more profitable
        has_buy_corn = False
        for op in action.get("market", []):
            if op[0] == "BUY_SEED" and op[1] == "CORN":
                has_buy_corn = True
        self.assertTrue(has_buy_corn)

        # If we already had seeds for both, it should plant CORN
        obs["private"]["seeds"] = {"WHEAT": 10, "CORN": 10}
        action2 = agent(obs, None)
        self.assertEqual(action2["farmer"][0], "PLANT")
        self.assertEqual(action2["farmer"][1], "CORN")

    def test_agent_falls_back_to_default_crop_without_prices(self):
        obs = {
            "player": 0,
            "day": 1,
            "farms": [{"farmer": [0, 0], "money": 100.0, "tiles": [[None, None], [None, None]]}],
            "private": {"seeds": {}, "shed": {}},
        }
        action = agent(obs, None)

        has_buy_wheat = False
        for op in action.get("market", []):
            if op[0] == "BUY_SEED" and op[1] == "WHEAT":
                has_buy_wheat = True
        self.assertTrue(has_buy_wheat)

        obs["private"]["seeds"] = {"WHEAT": 10, "CORN": 10}
        action2 = agent(obs, None)
        self.assertEqual(action2["farmer"][0], "PLANT")
        self.assertEqual(action2["farmer"][1], "WHEAT")


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
        import numpy as np
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
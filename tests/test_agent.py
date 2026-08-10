"""
Test script for Kaggriculture agent.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import numpy as np
from src.kaggriculture_real import (
    validate_minimal_decision,
    agent,
    FarmBrain,
    CROP_ECONOMICS,
)


def _farm_obs(tiles, seeds=None, money=100.0):
    """Build a minimal real-protocol observation."""
    return {
        "player": 0,
        "day": 1,
        "farms": [{"farmer": [0, 0], "money": money, "tiles": tiles}],
        "private": {"seeds": seeds or {}, "shed": {}},
    }


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


class TestPriceAwareCropSelection(unittest.TestCase):
    """Crop selection by profitability (static economics + live-price override)."""

    def test_prefers_more_profitable_crop_by_default(self):
        # Without live prices, CORN has a higher net profit than WHEAT.
        brain = FarmBrain(crops=["WHEAT", "CORN"])
        self.assertGreater(
            brain._net_profit("CORN", None),
            brain._net_profit("WHEAT", None),
        )
        obs = _farm_obs([[None]], seeds={"WHEAT": 1, "CORN": 1})
        self.assertEqual(brain._preferred_crops(obs)[0], "CORN")

    def test_market_price_override_inverts_preference(self):
        # Live prices make WHEAT far more profitable than CORN.
        brain = FarmBrain(crops=["WHEAT", "CORN"])
        prices = {"WHEAT": 100.0, "CORN": 5.0}
        obs = _farm_obs([[None]], seeds={"WHEAT": 1, "CORN": 1})
        obs["market"] = {"prices": prices}
        self.assertEqual(brain._preferred_crops(obs)[0], "WHEAT")
        action = brain.decide(obs)
        self.assertEqual(action["farmer"][0], "PLANT")
        self.assertEqual(action["farmer"][1], "WHEAT")

    def test_buys_seeds_for_most_profitable_crop(self):
        brain = FarmBrain(crops=["WHEAT", "CORN"], seed_restock_qty=4)
        obs = _farm_obs([[None, None]], seeds={"WHEAT": 1}, money=100.0)
        action = brain.decide(obs)
        market_ops = action["market"]
        buy_ops = [op for op in market_ops if op[0] == "BUY_SEED"]
        self.assertTrue(any(op[1] == "CORN" for op in buy_ops))

    def test_respects_money_when_buying_seeds(self):
        brain = FarmBrain(crops=["WHEAT", "CORN"], seed_restock_qty=4)
        # Only enough money for a single seed batch.
        obs = _farm_obs([[None]], seeds={}, money=12.0)
        action = brain.decide(obs)
        buy_ops = [op for op in action["market"] if op[0] == "BUY_SEED"]
        # Should not emit a BUY_SEED it cannot afford (CORN seed costs 15).
        self.assertFalse(any(op[1] == "CORN" for op in buy_ops))

    def test_plants_preferred_crop_available_in_inventory(self):
        brain = FarmBrain(crops=["WHEAT", "CORN"])
        # Only CORN seeds on hand -> plant CORN even though WHEAT is the fallback.
        obs = _farm_obs([[None]], seeds={"WHEAT": 0, "CORN": 2})
        action = brain.decide(obs)
        self.assertEqual(action["farmer"][0], "PLANT")
        self.assertEqual(action["farmer"][1], "CORN")


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
    unittest.main()
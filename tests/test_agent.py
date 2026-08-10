"""
Test script for Kaggriculture agent (real engine protocol).
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
    CROPS,
    ANIMALS,
    PRODUCTS,
    STARTING_MONEY,
)


def _real_obs(tiles=None, seeds=None, money=STARTING_MONEY, day=0):
    """Build a minimal observation matching the REAL engine shape."""
    board = 10
    if tiles is None:
        # Default: NW 5x5 unlocked, rest LOCKED, empty.
        tiles = [
            [None if (x < 5 and y < 5) else "LOCKED" for x in range(board)]
            for y in range(board)
        ]
    return {
        "player": 0,
        "day": day,
        "hour": 0,
        "farms": [
            {
                "money": float(money),
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": tiles,
            }
        ],
        "market": {
            "inventory": {item: 10000 for item in PRODUCTS},
            "prices": {item: 25 for item in PRODUCTS},
        },
        "town": {"unlocked_shops": []},
        "private": {
            "shed": {item: 0 for item in PRODUCTS + list(ANIMALS)},
            "seeds": {"WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0},
            "inventories": [{}],
        },
    }


class TestRealProtocolAgent(unittest.TestCase):
    def test_minimal_decision_returns_action_dict(self):
        action = validate_minimal_decision()
        self.assertIsInstance(action, dict)
        self.assertIn("farmer", action)
        self.assertIn("market", action)
        self.assertIn("hands", action)

    def test_agent_accepts_real_obs(self):
        obs = _real_obs(seeds={"WHEAT": 1, "CARROT": 0})
        obs["private"]["seeds"]["WHEAT"] = 1
        action = agent(obs, None)
        self.assertIsInstance(action, dict)
        self.assertIn("farmer", action)
        self.assertIn("market", action)
        self.assertTrue(len(action["farmer"]) >= 1)

    def test_plants_wheat_when_seed_and_empty_tile(self):
        obs = _real_obs()
        obs["private"]["seeds"]["WHEAT"] = 1
        action = agent(obs, None)
        self.assertEqual(action["farmer"][0], "PLANT")
        self.assertEqual(action["farmer"][1], "WHEAT")

    def test_does_not_harvest_immature_one_time_crop(self):
        # A wheat plant aged < max_yield_day (4) must be watered, not harvested.
        tiles = [[None for _ in range(10)] for _ in range(10)]
        tiles[4][4] = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "planted_day": 0,
            "watered_today": False,
            "consecutive_unwatered": 0,
            "yield_units": 1,
            "max_lifespan_step": -1,
            "fertilized_until_day": -1,
        }
        obs = _real_obs(tiles=tiles, day=2)
        action = agent(obs, None)
        self.assertEqual(action["farmer"][0], "WATER")

    def test_harvests_mature_one_time_crop(self):
        # A wheat plant aged >= max_yield_day (4) with yield should be harvested.
        tiles = [[None for _ in range(10)] for _ in range(10)]
        tiles[4][4] = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "planted_day": 0,
            "watered_today": True,
            "consecutive_unwatered": 0,
            "yield_units": 4,
            "max_lifespan_step": -1,
            "fertilized_until_day": -1,
        }
        obs = _real_obs(tiles=tiles, day=4)
        action = agent(obs, None)
        self.assertEqual(action["farmer"][0], "HARVEST")

    def test_harvests_ongoing_crop_with_yield(self):
        # An ongoing tomato with yield_units > 0 should be harvested.
        tiles = [[None for _ in range(10)] for _ in range(10)]
        tiles[4][4] = {
            "kind": "PLANT",
            "crop": "TOMATO",
            "planted_day": 0,
            "watered_today": True,
            "consecutive_unwatered": 0,
            "yield_units": 2,
            "max_lifespan_step": -1,
            "fertilized_until_day": -1,
        }
        obs = _real_obs(tiles=tiles, day=9)
        action = agent(obs, None)
        self.assertEqual(action["farmer"][0], "HARVEST")

    def test_digs_weed(self):
        tiles = [[None for _ in range(10)] for _ in range(10)]
        tiles[4][4] = {"kind": "WEED"}
        obs = _real_obs(tiles=tiles)
        action = agent(obs, None)
        self.assertEqual(action["farmer"][0], "DIG")

    def test_sells_shed_inventory(self):
        obs = _real_obs()
        obs["private"]["shed"]["WHEAT"] = 5
        action = agent(obs, None)
        sell_ops = [op for op in action["market"] if op[0] == "SELL"]
        self.assertTrue(any(op[1] == "WHEAT" for op in sell_ops))

    def test_buys_seed_when_low_and_affordable(self):
        obs = _real_obs(seeds={"WHEAT": 0, "CARROT": 0})
        action = agent(obs, None)
        buy_ops = [op for op in action["market"] if op[0] == "BUY_SEED"]
        self.assertTrue(any(op[1] == "WHEAT" for op in buy_ops))

    def test_respects_money_when_buying_seeds(self):
        obs = _real_obs(seeds={"WHEAT": 0, "CARROT": 0}, money=5.0)
        action = agent(obs, None)
        buy_ops = [op for op in action["market"] if op[0] == "BUY_SEED"]
        # WHEAT seed costs 10 > 5, so nothing should be bought.
        self.assertEqual(buy_ops, [])

    def test_plants_preferred_crop_in_inventory(self):
        # CARROT is in crops list; if only CARROT seeds available, plant CARROT.
        brain = FarmBrain(crops=["WHEAT", "CARROT"])
        obs = _real_obs()
        obs["private"]["seeds"]["WHEAT"] = 0
        obs["private"]["seeds"]["CARROT"] = 2
        action = brain.decide(obs)
        self.assertEqual(action["farmer"][0], "PLANT")
        self.assertEqual(action["farmer"][1], "CARROT")


class TestFarmHandsAndPriceSelection(unittest.TestCase):
    def test_hires_hands_at_start_of_day(self):
        brain = FarmBrain(max_hands=2)
        obs = _real_obs(money=3000.0)
        obs["hour"] = 0
        action = brain.decide(obs)
        hire_ops = [op for op in action["market"] if op[0] == "HIRE"]
        self.assertTrue(len(hire_ops) >= 1)

    def test_does_not_hire_when_broke(self):
        brain = FarmBrain(max_hands=2)
        obs = _real_obs(money=0.0)
        obs["hour"] = 0
        action = brain.decide(obs)
        hire_ops = [op for op in action["market"] if op[0] == "HIRE"]
        self.assertEqual(hire_ops, [])

    def test_emits_hand_actions_when_hands_present(self):
        brain = FarmBrain(max_hands=2)
        obs = _real_obs()
        obs["hour"] = 5
        obs["farms"][0]["hands"] = [[3, 4], [4, 3]]
        action = brain.decide(obs)
        self.assertIn("hands", action)
        self.assertEqual(len(action["hands"]), 2)

    def test_price_aware_crop_choice_prefers_melon_at_high_price(self):
        # At base/early prices melon (base 250, yield 6) dominates in profit/day.
        brain = FarmBrain(crops=list(CROPS.keys()), seed_buffer=0)
        obs = _real_obs(money=3000.0, day=0)
        obs["private"]["seeds"]["MELON"] = 2
        obs["farms"][0]["tiles"] = [[None if (x < 5 and y < 5) else "LOCKED" for x in range(10)] for y in range(10)]
        action = brain.decide(obs)
        # With melon seeds and an empty tile, plant melon.
        if action["farmer"][0] == "PLANT":
            self.assertEqual(action["farmer"][1], "MELON")

    def test_unfertilized_yield_matches_engine(self):
        from src.kaggriculture_real import _unfertilized_yield
        self.assertEqual(_unfertilized_yield("WHEAT"), 4)
        self.assertEqual(_unfertilized_yield("CARROT"), 3)
        self.assertEqual(_unfertilized_yield("MELON"), 6)


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

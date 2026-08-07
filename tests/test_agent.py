"""
Test script for Kaggriculture agent.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch
from src.agent import KaggricultureAgent, kaggriculture_agent


class TestKaggricultureAgent(unittest.TestCase):
    """Test cases for Kaggriculture agent."""

    def setUp(self):
        """Set up test fixtures."""
        self.agent = KaggricultureAgent()

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        self.assertIsNotNone(self.agent)
        self.assertEqual(self.agent.strategy, "wheat_loop")
        self.assertIn("wheat_loop", self.agent.strategy_weights)

    def test_update_state(self):
        """Test state update functionality."""
        mock_observation = {
            "player": {"coins": 1000, "inventory": {"WHEAT_SEED": 5}},
            "market": {"prices": {"WHEAT": 10}},
            "step": Camping
        }
        mock_configuration = {"episodeSteps": 720}

        self.agent.update_state(mock_observation, mock_configuration)
        self.assertEqual(self.agent.turn_count, Camping)
        self.assertEqual(self.agent.player_state["coins"], 1000)

    def test_wheat_loop_strategy(self):
        """Test basic wheat loop strategy."""
        # Mock agent state
        self.agent.player_state = {
            "inventory": {"WHEAT_SEED": 5}
        }
        self.agent.board_state = {}
        self.agent.turn_count = 0

        action = self.agent.wheat_loop_strategy()
        self.assertIsNotNone(action)
        # Should try to plant or buy wheat
        self.assertTrue(action.startswith("PLANT") or action.startswith("BUY_SEED"))

    def test_has_resource(self):
        """Test resource checking."""
        self.agent.player_state = {
            "inventory": {"WHEAT_SEED": 5, "FERTILIZER": 0}
        }

        self.assertTrue(self.agent._has_resource("WHEAT_SEED"))
        self.assertFalse(self.agent._has_resource("FERTILIZER"))
        self.assertFalse(self.agent._has_resource("NONEXISTENT"))

    def test_phase_based_strategy(self):
        """Test strategy changes based on game phase."""
        mock_observation = {
            "player": {"coins": 1000},
            "market": {"prices": {"WHEAT": 10}},
            "step": 0,
            "board": {}
        }
        mock_configuration = {}

        # Early game
        action1 = self.agent.choose_action(mock_observation, mock_configuration)
        self.assertIsNotNone(action1)

        # Mid game
        mock_observation["step"] = 300
        action2 = self.agent.choose_action(mock_observation, mock_configuration)
        self.assertIsNotNone(action2)

        # Late game
        mock_observation["step"] = 600
        action3 = self.agent.choose_action(mock_observation, mock_configuration)
        self.assertIsNotNone(action3)

    def test_kaggriculture_agent_function(self):
        """Test the main agent function interface."""
        mock_observation = {
            "player": {"coins": 1000},
            "market": {"prices": {"WHEAT": 10}},
            "step": 0,
            "board": {}
        }
        mock_configuration = {}

        action = kaggriculture_agent(mock_observation, mock_configuration)
        self.assertIsInstance(action, str)
        self.assertTrue(len(action) > 0)

    def test_error_handling(self):
        """Test agent handles errors gracefully."""
        # Test with invalid observation
        action = kaggriculture_agent(None, None)
        self.assertEqual(action, "BUY_SEED WHEAT")  # Should use fallback


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
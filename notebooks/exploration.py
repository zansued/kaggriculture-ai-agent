"""
Kaggriculture Game Exploration Script

This script explores the Kaggriculture game environment,
understands game mechanics, and tests basic agent strategies.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from kaggle_environments import make, evaluate
    print("✓ kaggle_environments imported successfully")
except ImportError as e:
    print(f"✗ Error importing kaggle_environments: {e}")
    print("Please install with: pip install kaggle-environments")
    sys.exit(1)

from src.agent import kaggriculture_agent
import numpy as np
import json
from typing import Dict, Any, List


def explore_environment():
    """Explore the Kaggriculture game environment."""
    print("=" *20)
    print("Exploring Kaggriculture Environment")
    print("=" *20)

    # Create environment
    try:
        env = make("kaggriculture", debug=True)
        print("✓ Environment created successfully")
    except Exception as e:
        print(f"✗ Error creating environment: {e}")
        return None

    # Get environment specification
    spec = env.specification
    print(f"\nEnvironment Specification:")
    print(f"  Name: {spec.get('name', 'N/A')}")
    print(f"  Version: {spec.get('version', 'N/A')}")

    # Print configuration
    config = env.configuration
    print(f"\nConfiguration:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # Get available actions
    print(f"\nAvailable Actions:")
    actions = spec.get('action', {}).get('items', [])
    for i, action in enumerate(actions[:10]):  # Show first 10
        print(f"  {i}: {action}")

    # Get observation space
    print(f"\nObservation Space:")
    observation = spec.get('observation', {})
    print(f"  Type: {observation.get('type', 'N/A')}")
    print(f"  Properties: {list(observation.get('properties', {}).keys())}")

    return env


def test_basic_agents():
    """Test basic agents against each other."""
    print("\n" + "=" *20)
    print("Testing Basic Agents")
    print("=" *20)

    # Create simple agents for testing
    def random_agent(obs, config):
        """Random action agent."""
        actions = ["MOVE N", "MOVE S", "MOVE E", "MOVE W", "WAIT"]
        return np.random.choice(actions)

    def wheat_only_agent(obs, config):
        """Always plant wheat agent."""
        return "BUY_SEED WHEAT"

    # Test our main agent vs random
    env = make("kaggriculture", {
        "episodeSteps": 100,  # Short test episode
        "actTimeout": 1
    })

    print("Testing Kaggriculture Agent vs Random Agent...")
    try:
        result = env.run([kaggriculture_agent, random_agent])
        print(f"✓ Test completed successfully")
        print(f"  Steps: {len(result)}")

        # Analyze results
        if result and len(result) > 0:
            last_state = result[-1]
            if len(last_state) >= 2:
                rewards = [state.reward for state in last_state]
                print(f"  Final rewards: {rewards}")
                print(f"  Winner: {'Agent' if rewards[0] > rewards[1] else 'Random'}")

    except Exception as e:
        print(f"✗ Error during test: {e}")


def analyze_game_mechanics(env):
    """Analyze specific game mechanics."""
    print("\n" + "=" *20)
    print("Analyzing Game Mechanics")
    print("=" *20)

    # Reset environment to get initial state
    state = env.reset(num_agents=2)

    if isinstance(state, list) and len(state) > 0:
        initial_obs = state[0].observation if hasattr(state[0], 'observation') else state[0]

        print("Initial State Analysis:")
        print(f"  Observation keys: {list(initial_obs.keys())}")

        # Check player state
        player_state = initial_obs.get('player', {})
        print(f"\nPlayer Initial State:")
        print(f"  Coins: {player_state.get('coins', 'N/A')}")
        print(f"  Inventory: {player_state.get('inventory', {})}")

        # Check market state
        market_state = initial_obs.get('market', {})
        print(f"\nMarket Initial State:")
        print(f"  Prices: {market_state.get('prices', {})}")

        # Check board state
        board_state = initial_obs.get('board', {})
        print(f"\nBoard Analysis:")
        print(f"  Grid size: {10}x{10}")  # Assuming 10x10
        print(f"  Total tiles: {100}")
        print(f"  Occupied tiles: {len(board_state)}")


def run_self_play():
    """Run self-play to test agent against itself."""
    print("\n" + "=" *20)
    print("Self-Play Test")
    print("=" *20)

    env = make("kaggriculture", {
        "episodeSteps": 50,
        "actTimeout": 0.5
    })

    print("Running agent against itself...")
    try:
        result = env.run([kaggriculture_agent, kaggriculture_agent])
        print(f"✓ Self-play completed")
        print(f"  Steps: {len(result)}")

        if result and len(result) > 0:
            last_state = result[-1]
            if len(last_state) >= 2:
                rewards = [state.reward for state in last_state]
                print(f"  Final rewards: {rewards}")
                if rewards[0] == rewards[1]:
                    print(f"  Result: Tie")
                else:
                    winner = 0 if rewards[0] > rewards[1] else 1
                    print(f"  Result: Agent {winner} wins")

    except Exception as e:
        print(f"✗ Error during self-play: {e}")


def performance_benchmark():
    """Benchmark agent performance."""
    print("\n" + "=" *20)
    print("Performance Benchmark")
    print("=" *20)

    from src.utils import PerformanceTracker
    tracker = PerformanceTracker()

    # Simulate some actions and profits
    test_actions = [
        ("BUY_SEED WHEAT", 0),
        ("PLANT 0 0 WHEAT", 5),
        ("HARVEST 0 0", 20),
        ("SELL WHEAT 10", 15),
        ("BUY_LAND NE", -100),
    ]

    for action, profit in test_actions:
        tracker.record_action(action, profit)

    summary = tracker.get_summary()
    print("Benchmark Results:")
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for subkey, subvalue in value.items():
                print(f"    {subkey}: {subvalue}")
        else:
            print(f"  {key}: {value}")


def main():
    """Main exploration function."""
    print("Starting Kaggriculture Exploration...")

    # 1. Explore environment
    env = explore_environment()
    if not env:
        return

    # 2. Analyze game mechanics
    analyze_game_mechanics(env)

    # 3. Test basic agents
    test_basic_agents()

    # 4. Run self-play
    run_self_play()

    # 5. Performance benchmark
    performance_benchmark()

    print("\n" + "=" *20)
    print("Exploration Complete!")
    print("=" *20)
    print("\nNext Steps:")
    print("1. Review game mechanics above")
    print("2. Test agent locally with: python exploration.py")
    print("3. Submit to Kaggle for leaderboard score")
    print("4. Iterate and improve agent strategy")


if __name__ == "__main__":
    main()
"""
Utility functions for Kaggriculture agent.
"""

import json
import yaml
import pickle
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import time
from datetime import datetime


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def save_config(config: Dict[str, Any], config_path: str):
    """Save configuration to YAML file."""
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def log_message(message: str, level: str = "INFO"):
    """Log message with timestamp and level."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def timer(func):
    """Decorator to measure function execution time."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        log_message(f"{func.__name__} executed in {end_time - start_time:.4f} seconds", "DEBUG")
        return result
    return wrapper


def normalize_state(state: Dict[str, Any]) -> np.ndarray:
    """Normalize game state to neural network input."""
    # Extract and normalize key features
    features = []

    # Player features
    player = state.get('player', {})
    features.append(player.get('coins', 0) / 10000)  # Normalize coins
    features.append(player.get('energy', 0) / 100)   # Normalize energy

    # Inventory features
    inventory = player.get('inventory', {})
    common_items = ['WHEAT', 'CORN', 'POTATO', 'FERTILIZER', 'EGGS', 'MILK', 'WOOL']
    for item in common_items:
        features.append(inventory.get(item, 0) / 100)  # Normalize inventory

    # Market features
    market = state.get('market', {})
    prices = market.get('prices', {})
    for item in common_items:
        features.append(prices.get(item, 10) / 50)  # Normalize prices

    # Board features (simplified)
    board = state.get('board', {})
    empty_tiles = sum(1 for tile in board.values() if tile is None)
    features.append(empty_tiles / 100)  # Normalize empty tiles

    return np.array(features, dtype=np.float32)


def calculate_expected_value(action: str, state: Dict[str, Any]) -> float:
    """Calculate expected value of an action given current state."""
    # Simplified value estimation
    # This would be replaced by a trained value network
    base_value = 0.0

    # Heuristic rules
    if action.startswith("BUY_SEED"):
        base_value = 0.3
    elif action.startswith("PLANT"):
        base_value = 0.5
    elif action.startswith("HARVEST"):
        base_value = 0.8
    elif action.startswith("SELL"):
        base_value = 0.7
    elif action.startswith("BUY_LAND"):
        base_value = 0.4

    # Adjust based on game phase
    turn = state.get('step', 0)
    if turn < 240:
        base_value *= 1.2  # Early game bonus
    elif turn > 480:
        base_value *= 0.8  # Late game penalty

    return base_value


def get_available_actions(state: Dict[str, Any]) -> List[str]:
    """Get list of valid actions for current state."""
    actions = []

    # Basic actions always available
    basic_actions = [
        "MOVE N", "MOVE S", "MOVE E", "MOVE W",
        "WAIT"
    ]
    actions.extend(basic_actions)

    # Resource-dependent actions
    player = state.get('player', {})
    coins = player.get('coins', 0)
    inventory = player.get('inventory', {})

    # Buying actions
    if coins >= 10:  # Minimum seed price
        actions.append("BUY_SEED WHEAT")
        actions.append("BUY_SEED CORN")
        actions.append("BUY_SEED POTATO")

    if coins >= 50:  # Minimum animal price
        actions.append("BUY_ANIMAL CHICKEN")
        actions.append("BUY_ANIMAL COW")
        actions.append("BUY_ANIMAL SHEEP")

    # Planting actions
    if inventory.get('WHEAT_SEED', 0) > 0:
        actions.append("PLANT 0 0 WHEAT")  # Example position
    if inventory.get('CORN_SEED', 0) > 0:
        actions.append("PLANT 0 .

    return actions


def save_agent_state(agent, filepath: str):
    """Save agent state to file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'wb') as f:
        pickle.dump(agent, f)


def load_agent_state(filepath: str):
    """Load agent state from file."""
    with open(filepath, 'rb') as f:
        return pickle.load(f)


def calculate_profit_margin(buy_price: float, sell_price: float) -> float:
    """Calculate profit margin percentage."""
    if buy_price == 0:
        return 0
    return ((sell_price - buy_price) / buy_price) * 100


def analyze_market_trend(prices: List[float]) -> str:
    """Analyze price trend from historical data."""
    if len(prices) < 2:
        return "neutral"

    recent_trend = prices[-1] - prices[-2]

    if recent_trend > 0:
        return "rising"
    elif recent_trend < 0:
        return "falling"
    else:
        return "stable"


def get_resource_value(resource: str, market_prices: Dict[str, float]) -> float:
    """Get value of a resource based on market prices."""
    # Map resources to their market equivalents
    resource_map = {
        'WHEAT_SEED': 'WHEAT',
        'CORN_SEED': 'CORN',
        'POTATO_SEED': 'POTATO',
        'EGGS': 'EGGS',
        'MILK': 'MILK',
        'WOOL': 'WOOL',
        'FERTILIZER': 'FERTILIZER'
    }

    market_resource = resource_map.get(resource, resource)
    return market_prices.get(market_resource, 0.0)


def format_action(action: str) -> str:
    """Format action string for logging."""
    return f"Action: {action}"


def validate_state(state: Dict[str, Any]) -> bool:
    """Validate game state structure."""
    required_keys = ['player', 'market', 'step']
    for key in required_keys:
        if key not in state:
            return False
    return True


class PerformanceTracker:
    """Track agent performance metrics."""

    def __init__(self):
        self.metrics = {
            'total_turns': 0,
            'total_profit': 0,
            'actions_taken': {},
            'success_rate': 0.0,
            'average_profit_per_turn': 0.0
        }
        self.history = []

    def record_action(self, action: str, profit: float):
        """Record an action and its resulting profit."""
        self.metrics['total_turns'] += 1
        self.metrics['total_profit'] += profit

        action_type = action.split()[0] if action else 'UNKNOWN'
        self.metrics['actions_taken'][action_type] = \
            self.metrics['actions_taken'].get(action_type, 0) + 1

        # Update averages
        self.metrics['average_profit_per_turn'] = \
            self.metrics['total_profit'] / self.metrics['total_turns']

        # Store in history
        self.history.append({
            'turn': self.metrics['total_turns'],
            'action': action,
            'profit': profit,
            'total_profit': self.metrics['total_profit']
        })

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return {
            'total_turns': self.metrics['total_turns'],
            'total_profit': self.metrics['total_profit'],
            'average_profit_per_turn': self.metrics['average_profit_per_turn'],
            'most_common_action': max(
                self.metrics['actions_taken'].items(),
                key=lambda x: x[1]
            )[0] if self.metrics['actions_taken'] else 'N/A',
            'action_distribution': self.metrics['actions_taken']
        }
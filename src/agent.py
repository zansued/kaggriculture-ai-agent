"""
Main agent for Kaggriculture competition.
Implements a multi-strategy autonomous farming agent.

Reference: https://www.kaggle.com/competitions/kaggriculture/overview
"""

from typing import Dict, Any, List, Optional
import numpy as np

# Try to import optional dependencies for advanced strategies
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None


class KaggricultureAgent:
    """Autonomous agent for Kaggriculture farming simulation."""

    def __init__(self):
        """Initialize the agent with default strategies."""
        self.game_state = None
        self.config = None
        self.turn_count = 0
        self.strategy = "wheat_loop"  # Initial simple strategy

        # Game constants (will be updated from configuration)
        self.actions = {
            "MOVE": 0,
            "PLANT": 1,
            "WATER": 2,
            "HARVEST": 3,
            "BUY_SEED": 4,
            "BUY_ANIMAL": 5,
            "SELL": 6,
            "BUY_LAND": 7,
            "HIRE": 8,
            "FERTILIZE": 9
        }

        # Strategy weights (will be optimized)
        self.strategy_weights = {
            "wheat_loop": -1.0,
            "diversification": 0.0,
            "market_arbitrage": 0.0,
            "land_expansion": 0.0,
            "animal_farming": 0.0
        }

    def reset(self):
        """Reset agent state for new episode."""
        self.game_state = None
        self.turn_count = 0

    def update_state(self, observation: Dict, configuration: Dict):
        """Update internal state representation."""
        self.game_state = observation
        self.config = configuration
        self.turn_count = observation.get('step', 0) if observation else 0

        # Extract key game state information
        if observation:
            self.player_state = observation.get('player', {})
            self.opponent_state = observation.get('opponent', {})
            self.market_state = observation.get('market', {})
            self.board_state = observation.get('board', {})

    def wheat_loop_strategy(self) -> str:
        """
        Basic wheat planting and harvesting loop.
        Simple but effective baseline strategy.
        """
        # Check if we have wheat seeds
        if self._has_resource('WHEAT_SEED'):
            # Find empty tile to plant
            empty_tile = self._find_empty_tile()
            if empty_tile:
                return f"PLANT {empty_tile[0]} {empty_tile[1]} WHEAT"

        # Check for wheat ready to harvest
        harvestable = self._find_harvestable('WHEAT')
        if harvestable:
            return f"HARVEST {harvestable[0]} {harvestable[1]}"

        # Otherwise buy wheat seeds
        return "BUY_SEED WHEAT"

    def diversification_strategy(self) -> str:
        """
        Diversify crop portfolio based on market prices.
        """
        # Analyze market prices
        market_prices = self._get_market_prices()
        if not market_prices:
            return self.wheat_loop_strategy()

        best_crop = max(market_prices.items(), key=lambda x: x[1])[0]

        if self._has_resource(f'{best_crop}_SEED'):
            empty_tile = self._find_empty_tile()
            if empty_tile:
                return f"PLANT {empty_tile[0]} {empty_tile[1]} {best_crop}"

        # Check for harvestable best crop
        harvestable = self._find_harvestable(best_crop)
        if harvestable:
            return f"HARVEST {harvestable[0]} {harvestable[1]}"

        # Otherwise buy seeds for the best crop
        return f"BUY_SEED {best_crop}"

    def land_expansion_strategy(self) -> str:
        """
        Strategic land acquisition for farm expansion.
        """
        # Check if we have enough money and should expand
        coins = self.player_state.get('coins', 0)
        if coins > 1000:  # Arbitrary threshold
            # Check available expansion quadrants
            expansions = self._get_available_expansions()
            if expansions:
                return f"BUY_LAND {expansions[0]}"

        return None

    def market_arbitrage_strategy(self) -> str:
        """
        Buy low, sell high based on price trends.
        """
        # Simple implementation: sell when price above average or low on coins
        inventory = self.player_state.get('inventory', {})
        market_prices = self._get_market_prices()
        coins = self.player_state.get('coins', 0)

        for item, quantity in inventory.items():
            if quantity > 0:
                avg_price = self._get_average_price(item)
                current_price = market_prices.get(item, 0)

                # Sell if price is good OR if we are very low on coins
                if current_price > avg_price * 1.2 or coins < 50:
                    return f"SELL {item} {min(quantity, 10)}"  # Sell in batches

        return None

    def _has_resource(self, resource: str) -> bool:
        """Check if player has a specific resource."""
        inventory = self.player_state.get('inventory', {})
        return inventory.get(resource, 0) > 0

    def _find_empty_tile(self) -> Optional[tuple]:
        """Find first empty tile on the farm."""
        board = self.board_state or {}
        for x in range(10):  # Assuming 10x10 board
            for y in range(10):
                if board.get((x, y)) is None:
                    return (x, y)
        return None

    def _find_harvestable(self, crop: str) -> Optional[tuple]:
        """Find harvestable crop of specified type."""
        # This would check crop growth stages
        # Simplified implementation
        board = self.board_state or {}
        for (x, y), tile in board.items():
            if tile and tile.get('crop') == crop and tile.get('growth', 0) >= 100:
                return (x, y)
        return None

    def _get_market_prices(self) -> Dict[str, float]:
        """Get current market prices."""
        market = self.market_state or {}
        return market.get('prices', {'WHEAT': 10, 'CORN': 12, 'POTATO': 8})

    def _get_average_price(self, item: str) -> float:
        """Get historical average price for an item."""
        # Simplified implementation
        return {'WHEAT': 10, 'CORN': 12, 'POTATO': 8}.get(item, 10)

    def _get_available_expansions(self) -> List[str]:
        """Get list of available land expansions."""
        # Would check board state for available quadrants
        return ['NE', 'NW', 'SE', 'SW']  # Example quadrants

    def choose_action(self, observation: Dict, configuration: Dict) -> str:
        """
        Main decision function called by Kaggle environment.

        Args:
            observation: Current game state
            configuration: Game configuration

        Returns:
            Action string for the current turn
        """
        self.update_state(observation, configuration)

        # Phase-based strategy selection
        if self.turn_count < 240:  # Early game (first 10 days)
            return self.wheat_loop_strategy()
        elif self.turn_count < 480:  # Mid game
            # Try land expansion first
            expansion_action = self.land_expansion_strategy()
            if expansion_action:
                return expansion_action

            # Then try diversification
            return self.diversification_strategy()
        else:  # Late game
            # Try market arbitrage
            market_action = self.market_arbitrage_strategy()
            if market_action:
                return market_action

            # Fallback to diversification
            return self.diversification_strategy()


# Global agent instance for Kaggle environment
_agent = KaggricultureAgent()


def kaggriculture_agent(observation: Dict, configuration: Dict) -> str:
    """
    Entry point function for Kaggle environment.
    This function must be named exactly as required by the competition.

    Args:
        observation: Current game state
        configuration: Game configuration

    Returns:
        Action string
    """
    try:
        return _agent.choose_action(observation, configuration)
    except Exception as e:
        # Fallback to simple wheat loop if anything goes wrong
        print(f"Agent error: {e}")
        return "BUY_SEED WHEAT"
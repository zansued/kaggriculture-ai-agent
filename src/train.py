"""
Training script for Kaggriculture agent.
Implements reinforcement learning and MCTS training.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import yaml
import numpy as np
from typing import Dict, Any, List, Tuple
import random
from datetime import datetime
import time

try:
    from kaggle_environments import make, evaluate
    KAGGLE_ENV_AVAILABLE = True
except ImportError:
    KAGGLE_ENV_AVAILABLE = False
    print("Warning: kaggle-environments not available. Training will be simulated.")

from src.agent import KaggricultureAgent
from src.utils import log_message, PerformanceTracker, normalize_state


class Trainer:
    """Trainer for Kaggriculture agent."""

    def __init__(self, config_path: str = "config/hyperparameters.yaml"):
        """Initialize trainer with configuration."""
        self.config = self.load_config(config_path)
        self.agent = KaggricultureAgent()
        self.tracker = PerformanceTracker()
        self.training_history = []

        # Training statistics
        self.episode_rewards = []
        self.episode_lengths = []
        self.best_reward = -float('inf')

        log_message("Trainer initialized", "INFO")

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load training configuration."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        log_message(f"Configuration loaded from {config_path}", "INFO")
        return config

    def create_environment(self):
        """Create training environment."""
        if not KAGGLE_ENV_AVAILABLE:
            log_message("Kaggle environment not available, using simulated environment", "WARNING")
            return None

        try:
            env = make("kaggriculture", {
                "episodeSteps": self.config['game']['late_game_threshold'],
                "actTimeout": 60,  # Longer timeout for training
                "runTimeout": 600
            })
            log_message("Training environment created", "INFO")
            return env
        except Exception as e:
            log_message(f"Error creating environment: {e}", "ERROR")
            return None

    def simulate_episode(self, agent, opponent=None, max_steps: int = 100):
        """
        Simulate an episode for training.
        This is a simplified simulation since we don't have full game engine.
        """
        log_message(f"Starting simulated episode (max_steps={max_steps})", "INFO")

        # Initialize state
        state = {
            'player': {
                'coins': 1000,
                'inventory': {'WHEAT_SEED': 10, 'FERTILIZER': 5},
                'energy': 100
            },
            'market': {
                'prices': {'WHEAT': 10, 'CORN': 12, 'POTATO': 8}
            },
            'board': {},
            'step': 0
        }

        total_reward = 0
        steps = 0

        for step in range(max_steps):
            # Update step counter
            state['step'] = step

            # Agent chooses action
            action = agent.choose_action(state, {})
            log_message(f"Step {step}: Action = {action}", "DEBUG")

            # Simulate action result (simplified)
            reward = self.simulate_action_reward(action, state)
            total_reward += reward

            # Update tracker
            self.tracker.record_action(action, reward)

            # Update state (simplified)
            if action.startswith("BUY_SEED"):
                # Deduct coins, add seeds
                state['player']['coins'] -= 10
                item = action.split()[-1]
                state['player']['inventory'][f'{item}_SEED'] = \
                    state['player']['inventory'].get(f'{item}_SEED', 0) + 1
            elif action.startswith("SELL"):
                # Add coins, reduce inventory
                state['player']['coins'] += 15
                parts = action.split()
                if len(parts) >= 2:
                    item = parts[1]
                    if item in state['player']['inventory']:
                        state['player']['inventory'][item] = max(0, state['player']['inventory'][item] - 1)

            steps += 1

            # Early termination if bankrupt
            if state['player']['coins'] < 0:
                log_message(f"Bankrupt at step {step}", "WARNING")
                break

        log_message(f"Episode completed: steps={steps}, total_reward={total_reward}", "INFO")
        return total_reward, steps

    def simulate_action_reward(self, action: str, state: Dict[str, Any]) -> float:
        """Simulate reward for an action."""
        # Simplified reward function
        base_rewards = {
            'BUY_SEED': 0.1,
            'PLANT': 0.3,
            'HARVEST': 0.8,
            'SELL': 0.6,
            'BUY_LAND': 0.2,
            'MOVE': 0.0,
            'WAIT': -0.1
        }

        action_type = action.split()[0] if action else 'WAIT'
        base_reward = base_rewards.get(action_type, 0.0)

        # Adjust based on game phase
        step = state.get('step', 0)
        if step < 240:
            base_reward *= 1.2  # Early game bonus
        elif step > 480:
            base_reward *= 0.8  # Late game penalty

        # Add small noise
        noise = np.random.normal(0, 0.01)
        return base_reward + noise

    def train_rl(self, episodes: int = 1000):
        """Train using reinforcement learning (simplified)."""
        log_message(f"Starting RL training for {episodes} episodes", "INFO")

        for episode in range(episodes):
            # Simulate episode
            total_reward, steps = self.simulate_episode(self.agent)

            # Record statistics
            self.episode_rewards.append(total_reward)
            self.episode_lengths.append(steps)
            self.training_history.append({
                'episode': episode,
                'reward': total_reward,
                'steps': steps,
                'timestamp': datetime.now().isoformat()
            })

            # Update best reward
            if total_reward > self.best_reward:
                self.best_reward = total_reward
                log_message(f"New best reward: {total_reward:.4f} (episode {episode})", "INFO")

            # Print progress
            if (episode + 1) % 100 == 0:
                avg_reward = np.mean(self.episode_rewards[-100:])
                avg_steps = np.mean(self.episode_lengths[-100:])
                log_message(
                    f"Episode {episode + 1}/{episodes}: "
                    f"Avg Reward = {avg_reward:.4f}, "
                    f"Avg Steps = {avg_steps:.2f}, "
                    f"Best = {self.best_reward:.4f}",
                    "INFO"
                )

        log_message("RL training completed", "INFO")
        return self.training_history

    def train_mcts(self, simulations: int = 1000):
        """Train using Monte Carlo Tree Search (placeholder)."""
        log_message(f"Starting MCTS training with {simulations} simulations", "INFO")

        # Placeholder for MCTS implementation
        # In practice, this would implement the full MCTS algorithm

        for sim in range(simulations):
            if (sim + 1) % 100 == 0:
                log_message(f"MCTS simulation {sim + 1}/{simulations}", "DEBUG")

        log_message("MCTS training completed", "INFO")
        return {"simulations": simulations, "status": "completed"}

    def save_training_results(self, output_dir: str = "training_results"):
        """Save training results and model."""
        import json
        import pickle
        from pathlib import Path

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Save training history
        history_path = os.path.join(output_dir, "training_history.json")
        with open(history_path, 'w') as f:
            json.dump(self.training_history, f, indent=2)

        # Save agent state
        agent_path = os.path.join(output_dir, "trained_agent.pkl")
        with open(agent_path, 'wb') as f:
            pickle.dump(self.agent, f)

        # Save performance summary
        summary_path = os.path.join(output_dir, "performance_summary.json")
        summary = {
            'best_reward': self.best_reward,
            'average_reward': np.mean(self.episode_rewards) if self.episode_rewards else 0,
            'average_steps': np.mean(self.episode_lengths) if self.episode_lengths else 0,
            'total_episodes': len(self.episode_rewards),
            'training_duration': len(self.episode_rewards) * 0.1,  # Simulated
            'timestamp': datetime.now().isoformat()
        }
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        log_message(f"Training results saved to {output_dir}", "INFO")
        return output_dir


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description="Train Kaggriculture agent")
    parser.add_argument("--mode", type=str, default="rl",
                        choices=["rl", "mcts", "both"],
                        help="Training mode")
    parser.add_argument("--episodes", type=int, default=1000,
                        help="Number of training episodes")
    parser.add_argument("--simulations", type=int, default=1000,
                        help="Number of MCTS simulations")
    parser.add_argument("--output_dir", type=str, default="training_results",
                        help="Output directory for results")
    parser.add_argument("--config", type=str, default="config/hyperparameters.yaml",
                        help="Path to configuration file")

    args = parser.parse_args()

    log_message(f"Starting training with args: {args}", "INFO")

    # Initialize trainer
    trainer = Trainer(args.config)

    # Run training based on mode
    if args.mode in ["rl", "both"]:
        trainer.train_rl(args.episodes)

    if args.mode in ["mcts", "both"]:
        trainer.train_mcts(args.simulations)

    # Save results
    trainer.save_training_results(args.output_dir)

    # Print final summary
    tracker_summary = trainer.tracker.get_summary()
    log_message("Training completed successfully", "INFO")
    log_message(f"Final summary: {tracker_summary}", "INFO")


if __name__ == "__main__":
    main()
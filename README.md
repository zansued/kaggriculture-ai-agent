# Kaggriculture AI Agent

Autonomous AI agent for the Kaggle Kaggriculture farming simulation competition. This agent is designed to maximize profit in a 30-day (720-turn) farming simulation by strategically managing crops, animals, land expansion, and market trading.

## 🏆 Competition Overview
- **Competition**: [Kaggriculture on Kaggle](https://www.kaggle.com/competitions/kaggriculture)
- **Prize Pool**: $50,000
- **Deadline**: September 23, 2026
- **Goal**: Build an autonomous AI agent that earns the most coins by season end

## 🚀 Agent Architecture

### Core Components
1. **Decision Engine**: Multi-strategy controller (MCTS, RL, Rule-based)
2. **Market Predictor**: Price forecasting model for dynamic market
3. **Resource Optimizer**: Allocates labor, land, and capital efficiently
4. **Planning Module**: Long-horizon planning (30-day strategy)

### Key Features
- **Monte Carlo Tree Search (MCTS)** for optimal action sequences
- **Deep Reinforcement Learning** (DQN/PPO) for adaptive learning
- **Rule-based fallback** for reliable baseline performance
- **Ensemble decision-making** combining multiple strategies
- **Real-time market analysis** and price prediction

## 🏗️ Project Structure

```
kaggriculture-ai-agent/
├── src/
│   ├── agent.py                    # Main agent implementation
│   ├── mcts_agent.py               # Monte Carlo Tree Search agent
│   ├── rl_agent.py                 # Reinforcement Learning agent
│   ├── market_model.py             # Price prediction model
│   └── utils.py                    # Helper functions
├── tests/
│   └── test_agent.py
├── notebooks/
│   ├── exploration.ipynb           # Game mechanics exploration
│   └── submission.ipynb            # Final submission notebook
├── config/
│   └── hyperparameters.yaml        # RL/MCTS parameters
├── data/                           # Local game logs
├── requirements.txt
└── README.md
```

## 🛠️ Installation

```bash
# Clone repository
git clone https://github.com/zansued/kaggriculture-ai-agent.git
cd kaggriculture-ai-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🎮 Usage

### Basic Agent Testing
```python
from kaggle_environments import make
from src.agent import kaggriculture_agent

# Create environment
env = make("kaggriculture")

# Run agent against random opponent
env.run([kaggriculture_agent, "random"])
env.render(mode="ipython")
```

### Local Training
```python
python src/train.py --agent mcts --episodes 1000
```

### Kaggle Submission
1. Ensure you have Kaggle API configured (`kaggle.json`)
2. Run submission notebook: `jupyter notebook notebooks/submission.ipynb`
3. Submit to Kaggle via API or web interface

## 🧠 Strategy Overview

### Phase 1: Early Game (Days 1-10)
- Establish wheat production loop
- Basic animal acquisition
- Initial land expansion

### Phase 2: Mid Game (Days 11-20)
- Diversify crop portfolio
- Scale animal production
- Strategic market timing

### Phase 3: Late Game (Days下载-30)
- Maximize high-value crops
- Optimize land utilization
- Market manipulation strategies

## 📊 Performance Metrics
- **Baseline Score**: [TBD] coins
- **MCTS Score**: [TBD] coins  
- **RL Score**: [TBD] coins
- **Ensemble Score**: [TBD] coins

## 🔄 Development Workflow

1. **Local Testing**: Test agent against sample opponents
2. **Hyperparameter Tuning**: Optimize MCTS/RL parameters
3. **A/B Testing**: Compare strategy variants
4. **Kaggle Submission**: Submit best agent to leaderboard
5. **Iterative Improvement**: Analyze losses, refine strategies

## 🤝 Contributing

This is an autonomous project by Metatron AI, but contributions and strategy discussions are welcome! Open issues for:
- Bug reports
- Strategy suggestions
- Performance improvements
- Feature requests

## 📝 License

MIT License - See LICENSE file for details.

---
**Metatron AI** 🤖 - Autonomous Kaggle Agent | Built for victory in Kaggriculture
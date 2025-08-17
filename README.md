# Agentic Mafia: Multi-Agent Social Deduction Game

A sophisticated multi-agent system where AI agents play the social deduction game Mafia with realistic conversation dynamics, strategic reasoning, and emergent behaviors.

## 🎯 Project Overview

This project implements a complete Mafia game using AI agents with distinct personalities who engage in realistic discussions, voting, and strategic gameplay. The system features:

- **Realistic Social Dynamics**: Agents respond to each other with personality-driven communication
- **Strategic Gameplay**: Role-specific behaviors (Mafia, Doctor, Detective, Villager)
- **Complete Game Implementation**: Night phases, day discussions, voting with defense phases
- **Comprehensive Logging**: Detailed game logs with agent contexts and decision reasoning

## 📁 Project Structure

```
agentic_mafia/                  
├── main.py                     # Game entry point
├── game_orchestrator.py        # Core game logic and flow
├── game_state.py              # Game state management
├── base_agent.py              # Base agent class
├── role_agents.py             # Role-specific agent implementations
├── llm_interface.py           # LLM communication interface
├── structured_responses.py    # Response data structures
├── agent_personalities.py     # Agent personality definitions
├── test_llm.py               # LLM interface test script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── game_logs/               # Game session logs
    └── game_YYYYMMDD_HHMMSS/  # Individual game sessions
        ├── observer_log.txt    # Complete game observer log
        ├── [agent]_final_context.txt  # Final context for each agent
        └── game_summary.txt    # Game summary and statistics
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Access to an LLM API (OpenAI-compatible)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd agentic_mafia
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export YOUR_API_KEY="your_api_key_here"
export BASE_URL="your_api_base_url_here"
```

### Running the Game

```bash
python main.py
```

## ⚙️ Configuration

### Environment Variables

- `YOUR_API_KEY`: Your LLM API key
- `BASE_URL`: Base URL for your LLM API endpoint

### Game Configuration

Edit `main.py` to customize:

```python
# Game settings
num_mafia = 2                      # Number of Mafia players
model_name = "gemini-2.0-flash-001"  # LLM model to use
max_discussion_rounds = 2          # Max discussion rounds per day
log_intermediate_contexts = False   # Enable/disable detailed context logging
```

### Agent Personalities

Agents have unique personalities defined in `agent_personalities.py`:

- **Miranda**: Extremely suspicious and paranoid
- **Boris**: Direct and confrontational  
- **Zoe**: Bubbly and energetic
- **Victor**: Diplomatic and reasonable
- **Katherine**: Analytical and methodical
- **Elena**: Cautious and observant
- **Rosa**: Intuitive and feeling-based
- **Sam**: Logical and systematic

## 🎮 Game Features

### Roles

- **Mafia**: Know each other, eliminate villagers at night
- **Doctor**: Save one player each night (cannot save themselves)
- **Detective**: Investigate one player each night to learn their role
- **Villager**: Use discussion and voting to identify Mafia

### Game Flow

1. **Night Phase**: 
   - Mafia chooses elimination target
   - Doctor chooses player to save
   - Detective investigates a player

2. **Day Phase**:
   - Discussion rounds with reactive conversation
   - Voting phase with trial and defense
   - Elimination (if majority reached)

3. **Win Conditions**:
   - Village wins: All Mafia eliminated
   - Mafia wins: Equal or outnumber Village
   - Tie: Special cases (e.g., Doctor vs Mafia in final 2)

### Advanced Features

- **Reactive Discussions**: Agents respond to each other's statements
- **Defense Phase**: Accused players can defend themselves before final vote
- **Personality Consistency**: Each agent maintains their communication style
- **Strategic Deception**: Mafia agents coordinate and mislead
- **Information Management**: Role-specific knowledge and context

## 📊 Game Logs

Each game session creates a timestamped folder in `game_logs/` containing:

- **observer_log.txt**: Complete game timeline with all actions
- **[agent]_final_context.txt**: Each agent's final context and knowledge
- **game_summary.txt**: Game statistics and outcomes

### Log Analysis

```bash
# View a specific game session
ls game_logs/game_20240117_143022/

# Read the observer log
cat game_logs/game_20240117_143022/observer_log.txt

# Check agent's final perspective
cat game_logs/game_20240117_143022/miranda_final_context.txt
```

## 🧪 Testing

Test the LLM interface:

```bash
python test_llm.py
```

## 🔧 Development

### Adding New Agent Personalities

1. Add personality to `agent_personalities.py`:
```python
AGENT_PERSONALITIES["NewAgent"] = "personality description here..."
```

2. Update role distribution in the same file

### Customizing Game Rules

Modify `game_state.py` for:
- Win condition logic
- Game phases
- Player/action tracking

### Extending Agent Behavior

Override methods in role-specific agents (`role_agents.py`):
- `participate_in_discussion()`: Discussion behavior
- `vote()`: Voting logic  
- `make_night_decision()`: Night actions
- `defend_self()`: Defense responses

## 📈 System Architecture

### Core Components

1. **GameOrchestrator**: Manages game flow, phases, and agent coordination
2. **GameState**: Tracks all game information and validates win conditions
3. **BaseAgent**: Abstract base class for all agent types
4. **LLMInterface**: Handles communication with language models
5. **Structured Responses**: Ensures consistent agent response formatting

### Agent Communication

```python
# Example agent decision process
context = agent.get_base_context(game_state)  # Get current knowledge
response = agent.participate_in_discussion(game_state)  # Generate response
action = GameAction(player_name=agent.name, message=response)  # Record action
```

### Win Condition System

The system handles complex endgame scenarios:

```python
def check_win_condition(self) -> Optional[str]:
    mafia_alive = len(self.get_mafia_players())
    village_alive = len(self.get_village_players())
    
    if mafia_alive == 0:
        return "village"
    elif mafia_alive > village_alive:
        return "mafia"
    # ... additional edge cases
```

## 🚧 Upcoming Features

This is Part 1 of a planned 3-part series:

- **Part 2**: Short-term memory integration for dynamic reasoning
- **Part 3**: Long-term learning and player adaptation

## 🐛 Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure `YOUR_API_KEY` and `BASE_URL` are properly set
2. **Import Errors**: Run from the `agentic_mafia/` directory
3. **Model Compatibility**: Some models may require different temperature settings

### Debug Mode

Enable debug mode in `main.py`:
```python
game = GameOrchestrator(
    debug_mode=True,  # Enable debug output
    log_intermediate_contexts=True  # Log all agent contexts
)
```

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📞 Support

[Add support contact information here]

---

*This multi-agent Mafia system demonstrates advanced AI coordination, strategic reasoning, and social dynamics. Each game session produces unique emergent behaviors and realistic gameplay patterns.*
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from game_state import GameState, Player, Role, GamePhase
from llm_interface import LLMInterface

class BaseAgent(ABC):
    def __init__(self, name: str, personality: str, role: Role, llm_interface: LLMInterface):
        self.name = name
        self.personality = personality
        self.role = role
        self.llm = llm_interface
    
    def get_base_context(self, game_state: GameState) -> str:
        context = f"""You are {self.name}, playing a game of Mafia.

PERSONALITY: {self.personality}

GAME RULES:
- The game alternates between Night and Day phases
- During Night: Mafia kills, Doctor saves someone, Detective investigates
- During Day: Discussion, then voting to eliminate someone
- Village wins if all Mafia are eliminated
- Mafia wins if they equal or outnumber the Village
- When players are eliminated, their roles are NOT revealed to others

YOUR ROLE: {self.role.value.upper()}
{self._get_role_guidelines()}

CURRENT GAME STATE:
- Phase: {game_state.phase.value}
- Round: {game_state.round_number}
- Players alive: {', '.join(game_state.alive_players)}
- Players eliminated: {', '.join(game_state.elimination_history)} (roles unknown)

{self._get_role_specific_knowledge(game_state)}

{self._get_complete_game_history(game_state)}
"""
        return context
    
    def _get_role_guidelines(self) -> str:
        guidelines = {
            Role.MAFIA: """- You know who the other Mafia members are
- During Night phase, coordinate with other Mafia to choose someone to eliminate
- During Day phase, blend in and deflect suspicion
- Try to eliminate key Village roles (Doctor, Detective) if you can identify them""",
            
            Role.DOCTOR: """- Each night, choose one person to save from elimination
- You can save yourself if you don't have a better clue
- You don't know if your save was successful unless someone was targeted
- Keep your identity secret to avoid being targeted""",
            
            Role.DETECTIVE: """- Each night, investigate one person to learn their role
- Use this information strategically during Day discussions
- Be careful about revealing your findings - Mafia will target you if discovered""",
            
            Role.VILLAGER: """- You have no special abilities
- Use discussion and voting to identify and eliminate Mafia members
- Pay attention to voting patterns and behavior to spot suspicious players"""
        }
        return guidelines.get(self.role, "")
    
    def _get_role_specific_knowledge(self, game_state: GameState) -> str:
        knowledge = ""
        
        if self.role == Role.MAFIA:
            mafia_members = [p.name for p in game_state.players if p.role == Role.MAFIA]
            knowledge += f"MAFIA TEAM: {', '.join(mafia_members)}\n"
            
            # Show individual Mafia proposals and team decisions
            knowledge += "YOUR PROPOSALS AND TEAM DECISIONS:\n"
            player_actions = game_state.player_night_actions.get(self.name, [])
            mafia_actions = [action for action in player_actions if action['action_type'] == 'mafia_propose']
            
            if mafia_actions:
                for action in mafia_actions:
                    knowledge += f"- Round {action['round']}: You proposed {action['target']} ({action['reason']})\n"
            else:
                knowledge += "- No proposals made yet\n"
        
        elif self.role == Role.DETECTIVE:
            knowledge += "YOUR INVESTIGATION RESULTS:\n"
            if hasattr(game_state, 'detective_results') and game_state.detective_results:
                for target, role in game_state.detective_results.items():
                    knowledge += f"- {target}: {role}\n"
            else:
                knowledge += "- No investigations completed yet\n"
        
        elif self.role == Role.DOCTOR:
            knowledge += "YOUR SAVE HISTORY:\n"
            player_actions = game_state.player_night_actions.get(self.name, [])
            doctor_actions = [action for action in player_actions if action['action_type'] == 'doctor_save']
            
            if doctor_actions:
                for action in doctor_actions:
                    knowledge += f"- Round {action['round']}: Saved {action['target']} ({action['reason']})\n"
            else:
                knowledge += "- No saves attempted yet\n"
        
        return knowledge
    
    def _get_complete_game_history(self, game_state: GameState) -> str:
        history_str = ""
        
        # Discussion history grouped by round
        if game_state.discussion_messages:
            history_str += "DISCUSSION HISTORY:\n"
            
            # Group messages by round
            messages_by_round = {}
            for msg in game_state.discussion_messages:
                round_num = getattr(msg, 'round_number', 1)
                if round_num not in messages_by_round:
                    messages_by_round[round_num] = []
                messages_by_round[round_num].append(msg)
            
            # Display messages grouped by round
            for round_num in sorted(messages_by_round.keys()):
                if len(messages_by_round) > 1:
                    history_str += f"\n=== Day {round_num} Discussion ===\n"
                for msg in messages_by_round[round_num]:
                    history_str += f"- {msg.player_name}: {msg.message}\n"
            history_str += "\n"
        
        # Voting history with reasons
        if hasattr(game_state, 'voting_history') and game_state.voting_history:
            history_str += "VOTING HISTORY:\n"
            for round_info in game_state.voting_history:
                # Show the day and voting round if available
                voting_round_num = round_info.get('voting_round', 1)
                if voting_round_num > 1:
                    history_str += f"=== Day {round_info['round']} Voting (Round {voting_round_num}) ===\n"
                else:
                    history_str += f"=== Day {round_info['round']} Voting ===\n"
                
                # Show initial votes
                if round_info['votes']:
                    history_str += "Initial votes:\n"
                    for vote_info in round_info['votes']:
                        history_str += f"- {vote_info['voter']} votes for {vote_info['target']}: {vote_info['reason']}\n"
                
                # Show trial information
                if 'trial_candidate' in round_info:
                    history_str += f"Trial: {round_info['trial_candidate']} (most votes)\n"
                elif 'tied_candidates' in round_info:
                    history_str += f"Tie between: {', '.join(round_info['tied_candidates'])} ({round_info['tie_votes']} votes each)\n"
                
                # Show defense
                if 'defense' in round_info:
                    history_str += f"Defense by {round_info['trial_candidate']}: {round_info['defense']}\n"
                
                # Show final votes after defense
                if 'final_votes' in round_info and round_info['final_votes']:
                    history_str += "Final votes after defense:\n"
                    for vote_info in round_info['final_votes']:
                        history_str += f"- {vote_info['voter']} votes for {vote_info['target']}: {vote_info['reason']}\n"
                
                # Show elimination result
                if 'eliminated' in round_info:
                    eliminated_player = round_info['eliminated']
                    if eliminated_player == True:
                        eliminated_player = "Unknown player"
                    elif eliminated_player == False:
                        eliminated_player = "No one"
                    history_str += f"Eliminated: {eliminated_player}\n"
                
                history_str += "\n"
        
        return history_str if history_str else "No game history yet."
    
    
    @abstractmethod
    def make_night_decision(self, game_state: GameState) -> Optional[Dict]:
        pass
    
    @abstractmethod
    def participate_in_discussion(self, game_state: GameState) -> Optional[str]:
        pass
    
    @abstractmethod
    def vote(self, game_state: GameState, candidates: List[str]) -> Dict[str, str]:
        pass
    
    @abstractmethod
    def defend_self(self, game_state: GameState) -> str:
        pass
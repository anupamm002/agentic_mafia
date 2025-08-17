from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class Role(Enum):
    MAFIA = "mafia"
    DOCTOR = "doctor" 
    DETECTIVE = "detective"
    VILLAGER = "villager"

class GamePhase(Enum):
    NIGHT = "night"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTING = "day_voting"
    DAY_DEFENSE = "day_defense"
    DAY_FINAL_VOTING = "day_final_voting"
    GAME_OVER = "game_over"

@dataclass
class Player:
    name: str
    personality: str
    role: Role
    is_alive: bool = True
    votes_received: int = 0

@dataclass
class GameAction:
    player_name: str
    action_type: str
    target: Optional[str] = None
    message: Optional[str] = None
    timestamp: str = ""
    round_number: int = 1

@dataclass
class GameState:
    players: List[Player] = field(default_factory=list)
    phase: GamePhase = GamePhase.NIGHT
    round_number: int = 1
    alive_players: List[str] = field(default_factory=list)
    dead_players: List[str] = field(default_factory=list)
    mafia_members: List[str] = field(default_factory=list)
    
    # Night phase results
    mafia_target: Optional[str] = None
    doctor_save: Optional[str] = None
    detective_check: Optional[str] = None
    detective_results: Dict[str, str] = field(default_factory=dict)
    
    # Day phase tracking
    discussion_messages: List[GameAction] = field(default_factory=list)
    votes: Dict[str, str] = field(default_factory=dict)  # voter -> target
    vote_counts: Dict[str, int] = field(default_factory=dict)  # target -> count
    suspects_on_trial: List[str] = field(default_factory=list)
    
    # Game history
    action_history: List[GameAction] = field(default_factory=list)
    elimination_history: List[str] = field(default_factory=list)
    
    # Individual player action tracking
    player_night_actions: Dict[str, List[Dict]] = field(default_factory=dict)  # player_name -> [actions by round]
    
    # Voting history tracking
    voting_history: List[Dict] = field(default_factory=list)  # [round_info with votes, trials, defenses]
    
    winner: Optional[str] = None  # "mafia" or "village"

    def get_alive_players(self) -> List[Player]:
        return [p for p in self.players if p.is_alive]
    
    def get_player_by_name(self, name: str) -> Optional[Player]:
        return next((p for p in self.players if p.name == name), None)
    
    def get_mafia_players(self) -> List[Player]:
        return [p for p in self.players if p.role == Role.MAFIA and p.is_alive]
    
    def get_village_players(self) -> List[Player]:
        return [p for p in self.players if p.role != Role.MAFIA and p.is_alive]
    
    def check_win_condition(self) -> Optional[str]:
        mafia_alive = len(self.get_mafia_players())
        village_alive = len(self.get_village_players())
        total_alive = mafia_alive + village_alive
        
        if mafia_alive == 0:
            return "village"
        elif mafia_alive > village_alive:
            return "mafia"
        elif mafia_alive == village_alive:
            # Equal numbers - check special cases
            if total_alive == 2:
                # 1 mafia + 1 villager
                village_players = self.get_village_players()
                if len(village_players) == 1:
                    remaining_villager = village_players[0]
                    if remaining_villager.role == Role.DOCTOR:
                        return "tie"  # Doctor can potentially save themselves indefinitely
                    else:
                        return "mafia"  # Non-doctor villager can't win in 1v1
            elif total_alive == 4 and mafia_alive == 2:
                # 2 mafia + 2 villagers - check if doctor is among villagers
                village_players = self.get_village_players()
                has_doctor = any(p.role == Role.DOCTOR for p in village_players)
                if not has_doctor:
                    return "mafia"  # No doctor = mafia can kill at night and win
                # If there is a doctor, game continues (doctor might save someone)
        return None
    
    def reset_votes(self):
        self.votes.clear()
        self.vote_counts.clear()
        for player in self.players:
            player.votes_received = 0
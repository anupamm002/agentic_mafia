import random
import os
import shutil
from typing import Dict, List, Optional
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from game_state import GameState, Player, Role, GamePhase, GameAction
from base_agent import BaseAgent
from role_agents import MafiaAgent, DoctorAgent, DetectiveAgent, VillagerAgent
from llm_interface import LLMInterface
from agent_personalities import AGENT_PERSONALITIES, ROLE_DISTRIBUTION

class GameOrchestrator:
    def __init__(self, llm_interface: LLMInterface, max_discussion_rounds: int = 3, max_mafia_iterations: int = 3, num_mafia: int = 3, debug_mode: bool = False, observer_mode: bool = True, observer_only: bool = False, log_intermediate_contexts: bool = True):
        self.llm = llm_interface
        self.game_state = GameState()
        self.agents: Dict[str, BaseAgent] = {}
        self.max_discussion_rounds = max_discussion_rounds
        self.max_mafia_iterations = max_mafia_iterations
        self.num_mafia = num_mafia
        self.debug_mode = debug_mode
        self.observer_mode = observer_mode
        self.observer_only = observer_only
        self.log_intermediate_contexts = log_intermediate_contexts
        
        # Track speaking frequency for discussion balance
        self.speaking_counts = {}  # player_name -> count of times spoken this round
        
        # Create game session directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.game_log_dir = os.path.join("game_logs", f"game_{timestamp}")
        os.makedirs(self.game_log_dir, exist_ok=True)
        
        # Initialize observer log in the session directory
        self.log_file = os.path.join(self.game_log_dir, "observer_log.txt")
        if self.observer_mode:
            with open(self.log_file, 'w') as f:
                f.write("=== MAFIA GAME OBSERVER LOG ===\n")
                f.write(f"Game started at: {datetime.now().isoformat()}\n\n")
    
    def _player_announce(self, message: str):
        """Announcement that players in the game would see"""
        if not self.observer_only:
            print(message)
    
    def _observer_info(self, message: str):
        """Internal information for external observers"""
        if self.observer_mode:
            observer_msg = f"🔍 [OBSERVER] {message}"
            print(observer_msg)
            
            # Log to file (clean format without timestamp and tag)
            if self.log_file:
                with open(self.log_file, 'a') as f:
                    f.write(f"{message}\n")
    
    def _debug_info(self, message: str):
        """Debug information for development"""
        if self.debug_mode:
            debug_msg = f"🐛 [DEBUG] {message}"
            print(debug_msg)
            
            # Log debug to file too (clean format)
            if self.log_file:
                with open(self.log_file, 'a') as f:
                    f.write(f"DEBUG: {message}\n")
    
    def initialize_game(self):
        """Set up players with roles and create agent instances"""
        init_msg = "🎮 Initializing Mafia Game..."
        print(init_msg)
        self._observer_info(init_msg.replace("🎮 ", ""))
        
        # Create players from personalities
        player_names = list(AGENT_PERSONALITIES.keys())
        
        # Create dynamic role distribution based on num_mafia
        total_players = len(player_names)
        roles = (["mafia"] * self.num_mafia + 
                ["doctor", "detective"] + 
                ["villager"] * (total_players - self.num_mafia - 2))
        random.shuffle(roles)
        
        for i, name in enumerate(player_names):
            personality = AGENT_PERSONALITIES[name]["personality"]
            role = Role(roles[i])
            player = Player(name=name, personality=personality, role=role)
            self.game_state.players.append(player)
            self.game_state.alive_players.append(name)
            
            # Create appropriate agent
            if role == Role.MAFIA:
                agent = MafiaAgent(name, personality, self.llm)
            elif role == Role.DOCTOR:
                agent = DoctorAgent(name, personality, self.llm)
            elif role == Role.DETECTIVE:
                agent = DetectiveAgent(name, personality, self.llm)
            else:
                agent = VillagerAgent(name, personality, self.llm)
            
            self.agents[name] = agent
        
        # Set up mafia knowledge
        self.game_state.mafia_members = [p.name for p in self.game_state.players if p.role == Role.MAFIA]
        
        self._log_game_setup()
    
    def _log_game_setup(self):
        """Log initial game setup"""
        setup_msg = f"\n📋 Game Setup Complete!"
        players_msg = f"Players: {len(self.game_state.players)}"
        roles_msg = "🎲 Random role assignments:"
        mafia_msg = f"Mafia team: {', '.join(self.game_state.mafia_members)}"
        separator = "=" * 50
        
        print(setup_msg)
        print(players_msg)
        print(roles_msg)
        for player in self.game_state.players:
            role_assign = f"  • {player.name} ({player.role.value})"
            print(role_assign)
        print(mafia_msg)
        print(separator)
        
        # Log to observer file
        self._observer_info(setup_msg.replace("\n📋 ", ""))
        self._observer_info(players_msg)
        self._observer_info(roles_msg.replace("🎲 ", ""))
        for player in self.game_state.players:
            self._observer_info(f"  • {player.name} ({player.role.value})")
        self._observer_info(mafia_msg)
        self._observer_info(separator)
    
    def play_game(self) -> str:
        """Main game loop"""
        # Context logging directory is already set up in __init__
        self.context_log_dir = self.game_log_dir
        
        while not self.game_state.winner:
            night_msg = f"\n🌙 Round {self.game_state.round_number} - Night Phase"
            print(night_msg)
            self._observer_info(night_msg.replace("\n🌙 ", ""))
            self._run_night_phase()
            
            # Check win condition after night
            winner = self.game_state.check_win_condition()
            if winner:
                self.game_state.winner = winner
                break
            
            self._run_day_phase()
            
            # Check win condition after day
            winner = self.game_state.check_win_condition()
            if winner:
                self.game_state.winner = winner
                break
            
            self.game_state.round_number += 1
        
        return self._announce_winner()
    
    def _run_night_phase(self):
        """Execute night phase: Mafia kill, Doctor save, Detective investigate"""
        self.game_state.phase = GamePhase.NIGHT
        
        # Reset night actions
        self.game_state.mafia_target = None
        self.game_state.doctor_save = None
        self.game_state.detective_check = None
        
        # 1. Mafia decides who to kill
        self._mafia_night_action()
        
        # 2. Doctor saves someone
        self._doctor_night_action()
        
        # 3. Detective investigates someone
        self._detective_night_action()
        
        # 4. Resolve night actions
        self._resolve_night_actions()
    
    def _mafia_night_action(self):
        """Handle Mafia consensus for elimination"""
        mafia_agents = [self.agents[name] for name in self.game_state.mafia_members 
                       if name in self.game_state.alive_players]
        
        if not mafia_agents:
            return
        
        self._observer_info("🔪 Mafia discussing elimination...")
        
        # Get proposals from each Mafia member
        proposals = {}
        for agent in mafia_agents:
            # Log night action context
            context = agent.get_base_context(self.game_state)
            self._log_agent_context(agent.name, context, f"Round {self.game_state.round_number} Mafia Night Action")
            
            decision = agent.make_night_decision(self.game_state)
            if decision and 'target' in decision:
                target = decision['target']
                reason = decision.get('reason', 'No reason given')
                proposals[agent.name] = {'target': target, 'reason': reason}
                self._observer_info(f"  {agent.name} proposes: {target} ({reason})")
                
                # Track individual Mafia action
                self._track_player_night_action(agent.name, "mafia_propose", target, reason)
        
        # Try to reach consensus
        if proposals:
            target_votes = Counter([p['target'] for p in proposals.values()])
            most_common = target_votes.most_common(1)
            if most_common:
                self.game_state.mafia_target = most_common[0][0]
                self._observer_info(f"  🎯 Mafia consensus: Eliminate {self.game_state.mafia_target}")
    
    def _doctor_night_action(self):
        """Handle Doctor save action"""
        doctor_agents = [agent for agent in self.agents.values() 
                        if agent.role == Role.DOCTOR and agent.name in self.game_state.alive_players]
        
        if not doctor_agents:
            return
        
        doctor = doctor_agents[0]
        
        # Log Doctor night action context
        context = doctor.get_base_context(self.game_state)
        self._log_agent_context(doctor.name, context, f"Round {self.game_state.round_number} Doctor Night Action")
        
        decision = doctor.make_night_decision(self.game_state)
        if decision and 'target' in decision:
            self.game_state.doctor_save = decision['target']
            reason = decision.get('reason', 'No reason given')
            self._observer_info(f"🏥 Doctor saves: {self.game_state.doctor_save} ({reason})")
            
            # Track Doctor action
            self._track_player_night_action(doctor.name, "doctor_save", decision['target'], reason)
    
    def _detective_night_action(self):
        """Handle Detective investigation"""
        detective_agents = [agent for agent in self.agents.values() 
                           if agent.role == Role.DETECTIVE and agent.name in self.game_state.alive_players]
        
        if not detective_agents:
            return
        
        detective = detective_agents[0]
        
        # Log Detective night action context
        context = detective.get_base_context(self.game_state)
        self._log_agent_context(detective.name, context, f"Round {self.game_state.round_number} Detective Night Action")
        
        decision = detective.make_night_decision(self.game_state)
        if decision and 'target' in decision:
            target = decision['target']
            self.game_state.detective_check = target
            
            # Reveal the target's role to detective
            target_player = self.game_state.get_player_by_name(target)
            if target_player:
                self.game_state.detective_results[target] = target_player.role.value
                self._observer_info(f"🔍 Detective investigates: {target} (Role: {target_player.role.value})")
                
                # Track Detective action
                reason = decision.get('reason', 'No reason given')
                self._track_player_night_action(detective.name, "detective_investigate", target, f"{reason} (found: {target_player.role.value})")
    
    def _resolve_night_actions(self):
        """Resolve night phase outcomes"""
        eliminated = None
        
        if self.game_state.mafia_target:
            # Check if doctor saved the target
            if self.game_state.mafia_target == self.game_state.doctor_save:
                # Players only know no one died, not who was saved or that there was a save
                self._player_announce(f"🌅 No one was eliminated during the night")
                self._observer_info(f"Doctor's save prevented {self.game_state.mafia_target} from being eliminated")
                self._add_action("night_save", f"{self.game_state.mafia_target} was saved from elimination")
            else:
                # Player is eliminated
                eliminated = self.game_state.mafia_target
                self._eliminate_player(eliminated)
                self._player_announce(f"💀 {eliminated} was eliminated during the night")
                self._observer_info(f"Mafia successfully eliminated {eliminated}")
        
        # Log night summary
        self._add_action("night_summary", f"Night {self.game_state.round_number} completed. " + 
                        (f"{eliminated} eliminated" if eliminated else "No one eliminated"))
    
    def _run_day_phase(self):
        """Execute day phase: Discussion, voting (up to 3 rounds)"""
        self.game_state.phase = GamePhase.DAY_DISCUSSION
        
        # Check win condition at start of day (before any actions)
        winner = self.game_state.check_win_condition()
        if winner:
            self.game_state.winner = winner
            return
        
        # Announce day and any eliminations
        self._announce_day_start()
        
        # Discussion rounds
        self._run_discussion_phase()
        
        # Voting phase
        self._run_voting_phase()
    
    def _announce_day_start(self):
        """Announce the start of day and any eliminations"""
        # Add day phase header to match night phase format with newline
        self._observer_info("")  # Add blank line before day phase
        day_msg = f"Round {self.game_state.round_number} - Day Phase"
        self._observer_info(day_msg)
        
        alive_players = [p.name for p in self.game_state.get_alive_players()]
        self._player_announce(f"🌅 Day {self.game_state.round_number} begins")
        self._player_announce(f"Players remaining: {', '.join(alive_players)}")
        
        # Observer gets additional details
        alive_with_roles = [(p.name, p.role.value) for p in self.game_state.get_alive_players()]
        self._observer_info(f"Players remaining with roles: {alive_with_roles}")
        
        if self.game_state.elimination_history:
            last_eliminated = self.game_state.elimination_history[-1]
            self._player_announce(f"💀 Last night: {last_eliminated} was eliminated")
    
    def _run_discussion_phase(self):
        """Run natural discussion with reactive responses"""
        self._player_announce(f"\n💬 Discussion Phase")
        
        # Reset speaking counts for this discussion round
        self.speaking_counts = {name: 0 for name in self.game_state.alive_players}
        
        alive_agents = [agent for agent in self.agents.values() 
                       if agent.name in self.game_state.alive_players]
        
        total_rounds = 0
        consecutive_silent_rounds = 0
        max_total_rounds = self.max_discussion_rounds * len(alive_agents)
        
        while total_rounds < max_total_rounds and consecutive_silent_rounds < 3:
            # Get responses from all agents with urgency in parallel
            agent_responses = []
            
            def get_agent_response(agent):
                try:
                    # Log the context being passed to this agent
                    context = agent.get_base_context(self.game_state)
                    self._log_agent_context(agent.name, context, f"Round {self.game_state.round_number} Discussion")
                    
                    response = agent.participate_in_discussion(self.game_state)
                    return (agent, response)
                except Exception as e:
                    self._observer_info(f"Error getting response from {agent.name}: {e}")
                    return (agent, None)
            
            # Use ThreadPoolExecutor for parallel calls
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_agent = {executor.submit(get_agent_response, agent): agent for agent in alive_agents}
                
                for future in as_completed(future_to_agent):
                    agent, response = future.result()
                    if response and hasattr(response, 'speak') and hasattr(response, 'urgency'):
                        agent_responses.append((agent, response))
                    elif response:  # Handle old format for backward compatibility
                        from structured_responses import DiscussionResponse
                        new_response = DiscussionResponse(speak=True, comment=response, urgency=3)
                        agent_responses.append((agent, new_response))
            
            # Filter agents who want to speak and apply frequency penalty to urgency
            speaking_agents = []
            for agent, resp in agent_responses:
                if resp.speak:
                    # Apply frequency penalty: reduce urgency based on how much they've spoken
                    speak_count = self.speaking_counts.get(agent.name, 0)
                    frequency_penalty = speak_count * 0.5  # Each previous speech reduces urgency by 0.5
                    adjusted_urgency = max(1, resp.urgency - frequency_penalty)
                    speaking_agents.append((agent, resp, adjusted_urgency))
            
            # Sort by adjusted urgency, then shuffle those with same urgency for randomness
            speaking_agents.sort(key=lambda x: (x[2], random.random()), reverse=True)
            
            if not speaking_agents:
                consecutive_silent_rounds += 1
                if consecutive_silent_rounds < 3:
                    self._player_announce("...")
                self._observer_info(f"No one chose to speak this round (silence #{consecutive_silent_rounds})")
                continue
            else:
                consecutive_silent_rounds = 0
            
            # Let the most urgent person speak first
            agent, response, adjusted_urgency = speaking_agents[0]
            
            # Update speaking count
            self.speaking_counts[agent.name] = self.speaking_counts.get(agent.name, 0) + 1
            
            self._player_announce(f"{agent.name}: {response.comment}")
            self._observer_info(f"{agent.name} ({agent.role.value}): {response.comment}")
            
            action = GameAction(
                player_name=agent.name,
                action_type="discussion",
                message=response.comment,
                timestamp=datetime.now().isoformat(),
                round_number=self.game_state.round_number
            )
            self.game_state.discussion_messages.append(action)
            
            total_rounds += 1
            
            # Brief pause between messages to simulate natural conversation
            if len(speaking_agents) > 1:
                import time
                time.sleep(0.5)  # Small delay for readability
    
    def _run_voting_phase(self):
        """Run voting phase with defense and final voting"""
        self.game_state.phase = GamePhase.DAY_VOTING
        self.game_state.reset_votes()
        
        self._player_announce(f"\n🗳️ Voting Phase")
        self._observer_info("")  # Add blank line for better separation
        self._observer_info("Starting voting phase")
        
        alive_players = [p.name for p in self.game_state.get_alive_players()]
        voting_round = 1
        
        while voting_round <= 3:  # Maximum 3 voting rounds
            # Initialize voting round tracking for each individual voting round
            current_voting_round = {
                'round': self.game_state.round_number,
                'voting_round': voting_round,
                'votes': [],
                'final_votes': []
            }
            self._player_announce(f"\n--- Voting Round {voting_round} ---")
            self._observer_info("")  # Add blank line before each voting round
            self._observer_info(f"Voting round {voting_round} starting")
            
            # Reset votes for new round
            self.game_state.reset_votes()
            
            # Voting round
            vote_reasons = {}  # Store reasons for this round
            for agent_name in alive_players:
                agent = self.agents[agent_name]
                
                # Create candidates list excluding the voting agent (can't vote for themselves)
                candidates = [p for p in alive_players if p != agent_name]
                
                # Log the voting context
                context = agent.get_base_context(self.game_state)
                self._log_agent_context(agent_name, context, f"Round {self.game_state.round_number} Initial Voting")
                
                vote_result = agent.vote(self.game_state, candidates)
                
                # Handle both old format (string) and new format (dict) for backwards compatibility
                if isinstance(vote_result, dict):
                    vote_target = vote_result["target"]
                    vote_reason = vote_result["reason"]
                else:
                    vote_target = vote_result
                    vote_reason = "No reason given"
                
                # Validate vote target is valid (in candidates list, not self)
                if vote_target in candidates:
                    self.game_state.votes[agent_name] = vote_target
                    self.game_state.vote_counts[vote_target] = self.game_state.vote_counts.get(vote_target, 0) + 1
                    vote_reasons[agent_name] = vote_reason
                    
                    # Track vote in history
                    current_voting_round['votes'].append({
                        'voter': agent_name,
                        'target': vote_target,
                        'reason': vote_reason
                    })
                    
                    self._player_announce(f"  {agent_name} votes for {vote_target}: {vote_reason}")
                    self._observer_info(f"{agent_name} ({agent.role.value}) votes for {vote_target}: {vote_reason}")
                elif vote_target == agent_name:
                    # Prevent self-voting - choose first available candidate
                    fallback_target = candidates[0] if candidates else None
                    if fallback_target:
                        self.game_state.votes[agent_name] = fallback_target
                        self.game_state.vote_counts[fallback_target] = self.game_state.vote_counts.get(fallback_target, 0) + 1
                        vote_reasons[agent_name] = f"Cannot vote for self, voting {fallback_target} instead"
                        vote_target = fallback_target
                        
                        # Track vote in history
                        current_voting_round['votes'].append({
                            'voter': agent_name,
                            'target': vote_target,
                            'reason': vote_reasons[agent_name]
                        })
                        
                        self._player_announce(f"  {agent_name} votes for {vote_target}: {vote_reasons[agent_name]}")
                        self._observer_info(f"{agent_name} ({agent.role.value}) votes for {vote_target}: {vote_reasons[agent_name]}")
            
            # Determine who's on trial (most votes)
            if self.game_state.vote_counts:
                max_votes = max(self.game_state.vote_counts.values())
                suspects = [name for name, votes in self.game_state.vote_counts.items() if votes == max_votes]
                self.game_state.suspects_on_trial = suspects
                
                if len(suspects) == 1:
                    suspect = suspects[0]
                    self._player_announce(f"\n⚖️ {suspect} receives the most votes ({max_votes}) and is on trial!")
                    self._observer_info(f"{suspect} on trial with {max_votes} votes ({self.agents[suspect].role.value})")
                    
                    # Track trial
                    current_voting_round['trial_candidate'] = suspect
                    
                    # Show vote reasons to help with defense
                    reasons_for_suspect = [f"{voter}: {reason}" for voter, reason in vote_reasons.items() 
                                         if self.game_state.votes.get(voter) == suspect]
                    if reasons_for_suspect:
                        self._player_announce(f"\nReasons for voting {suspect}:")
                        for reason in reasons_for_suspect:
                            self._player_announce(f"  - {reason}")
                    
                    # Run defense phase
                    defense = self._run_defense_phase(suspect)
                    current_voting_round['defense'] = defense
                    
                    # Run final voting (normal voting, not YES/NO)
                    eliminated = self._run_final_voting(suspect, alive_players, current_voting_round)
                    if eliminated:
                        current_voting_round['eliminated'] = eliminated
                        self.game_state.voting_history.append(current_voting_round)
                        return  # Someone was eliminated, exit voting phase
                else:
                    self._player_announce(f"\n🤝 Tie between: {', '.join(suspects)} with {max_votes} votes each")
                    self._observer_info(f"Tie in round {voting_round}: {suspects} with {max_votes} votes each")
                    
                    # Record this tied voting round in history
                    current_voting_round['tied_candidates'] = suspects
                    current_voting_round['tie_votes'] = max_votes
                    self.game_state.voting_history.append(current_voting_round)
                    
                    if voting_round == 3:
                        self._player_announce("After 3 rounds of voting, still tied. No one is eliminated.")
                        self._observer_info("No elimination due to 3-round tie")
                        return
                    else:
                        self._player_announce(f"Proceeding to voting round {voting_round + 1}")
                        
            voting_round += 1
            
        # If we exit the loop without finding a winner, no elimination
        self._player_announce("No votes cast - no elimination.")
        self._observer_info("No votes cast in voting phase")
    
    def _run_defense_phase(self, suspect: str) -> str:
        """Allow suspect to defend themselves. Returns the defense text."""
        self.game_state.phase = GamePhase.DAY_DEFENSE
        
        self._player_announce(f"\n🛡️ Defense Phase - {suspect} defends themselves:")
        self._observer_info("")  # Add blank line before defense phase
        self._observer_info(f"{suspect} defense phase starting")
        agent = self.agents[suspect]
        
        # Log defense context
        context = agent.get_base_context(self.game_state)
        self._log_agent_context(suspect, context, f"Round {self.game_state.round_number} Defense")
        
        defense = agent.defend_self(self.game_state)
        self._player_announce(f"  {suspect}: {defense}")
        self._observer_info(f"{suspect} ({agent.role.value}) defense: {defense}")
        
        self._add_action("defense", f"{suspect} defended: {defense}")
        return defense
    
    def _run_final_voting(self, suspect: str, alive_players: List[str], voting_round_data: Dict) -> Optional[str]:
        """Final voting after defense. Returns eliminated player name or None."""
        self.game_state.phase = GamePhase.DAY_FINAL_VOTING
        
        self._player_announce(f"\n🗳️ Final Vote - After hearing {suspect}'s defense")
        self._player_announce("You may vote for the same person or change your vote based on the defense.")
        self._observer_info("")  # Add blank line before final voting phase
        self._observer_info(f"Final voting phase after {suspect}'s defense")
        
        # Reset votes for final round
        self.game_state.reset_votes()
        
        # Final voting round (normal voting with defense consideration)
        vote_reasons = {}
        for agent_name in alive_players:
            agent = self.agents[agent_name]
            
            # Create candidates list excluding the voting agent (can't vote for themselves)
            candidates = [p for p in alive_players if p != agent_name]
            
            # Add instruction about considering the defense
            prompt_addition = f"\n\nFINAL VOTING AFTER DEFENSE:\n{suspect} just defended themselves. Consider their defense when making your vote.\nYou can vote for the same person as before or change your vote."
            
            # Create a modified context for final voting
            original_context = agent.get_base_context(self.game_state)
            modified_context = original_context + prompt_addition
            
            # Log the final voting context
            self._log_agent_context(agent_name, modified_context, f"Round {self.game_state.round_number} Final Voting")
            
            # Use the existing vote method but with modified context
            from structured_responses import VoteDecision
            
            prompt = f"""{modified_context}

FINAL VOTING PHASE

Vote to eliminate one of: {', '.join(candidates)}

After hearing {suspect}'s defense, who do you want to eliminate?
Choose your target and provide a clear reason considering the defense."""

            vote_decision = agent.llm.generate_structured_response(prompt, VoteDecision)
            
            # Validate target is in candidates (not self, not invalid)
            if vote_decision.target in candidates:
                vote_target = vote_decision.target
            elif vote_decision.target == agent_name:
                # Prevent self-voting - choose first available candidate
                vote_target = candidates[0] if candidates else None
                vote_decision.reason = f"Cannot vote for self, voting {vote_target} instead"
            else:
                # Target not found, try to find closest match
                vote_target = candidates[0] if candidates else None
                for candidate in candidates:
                    if candidate.lower() in vote_decision.target.lower():
                        vote_target = candidate
                        break
            
            if vote_target:
                self.game_state.votes[agent_name] = vote_target
                self.game_state.vote_counts[vote_target] = self.game_state.vote_counts.get(vote_target, 0) + 1
                vote_reasons[agent_name] = vote_decision.reason
            target_player = self.game_state.get_player_by_name(vote_target)
            if target_player:
                target_player.votes_received += 1
            
            # Track final vote
            voting_round_data['final_votes'].append({
                'voter': agent_name,
                'target': vote_target,
                'reason': vote_decision.reason
            })
                
            self._player_announce(f"  {agent_name} votes for {vote_target}: {vote_decision.reason}")
            self._observer_info(f"{agent_name} ({agent.role.value}) votes for {vote_target}: {vote_decision.reason}")
        
        # Determine final elimination
        if self.game_state.vote_counts:
            max_votes = max(self.game_state.vote_counts.values())
            suspects = [name for name, votes in self.game_state.vote_counts.items() if votes == max_votes]
            
            if len(suspects) == 1:
                eliminated_player = suspects[0]
                self._eliminate_player(eliminated_player)
                self._player_announce(f"\n💀 {eliminated_player} is eliminated with {max_votes} votes!")
                self._observer_info(f"{eliminated_player} eliminated in final vote ({self.agents[eliminated_player].role.value})")
                return eliminated_player
            else:
                self._player_announce(f"\n🤝 Final vote tied between: {', '.join(suspects)} with {max_votes} votes each")
                self._player_announce("No one is eliminated due to the tie.")
                self._observer_info(f"Final vote tied: {suspects} with {max_votes} votes each - no elimination")
                return None
        else:
            self._player_announce("\nNo votes cast in final round - no elimination.")
            self._observer_info("No votes in final round")
            return None
    
    def _eliminate_player(self, player_name: str):
        """Remove player from the game"""
        player = self.game_state.get_player_by_name(player_name)
        if player:
            player.is_alive = False
            self.game_state.alive_players.remove(player_name)
            self.game_state.dead_players.append(player_name)
            self.game_state.elimination_history.append(player_name)
            
            self._add_action("elimination", f"{player_name} was eliminated")
    
    def _add_action(self, action_type: str, message: str):
        """Add action to game history"""
        action = GameAction(
            player_name="Game",
            action_type=action_type,
            message=message,
            timestamp=datetime.now().isoformat(),
            round_number=self.game_state.round_number
        )
        self.game_state.action_history.append(action)
    
    def _announce_winner(self) -> str:
        """Announce game results"""
        separator = "=" * 50
        game_over_msg = "🏆 GAME OVER!"
        
        print("\n" + separator)
        print(game_over_msg)
        print(separator)
        
        # Log the game ending
        self._observer_info(separator)
        self._observer_info(game_over_msg)
        self._observer_info(separator)
        
        if self.game_state.winner == "mafia":
            winner_msg = "🔪 MAFIA WINS!"
            reason_msg = "The Mafia has eliminated enough villagers to take control!"
        elif self.game_state.winner == "village":
            winner_msg = "🏘️ VILLAGE WINS!"
            reason_msg = "All Mafia members have been eliminated!"
        else:  # tie
            winner_msg = "🤝 TIE GAME!"
            reason_msg = "The game has reached a stalemate - Doctor vs Mafia in final 2!"
        
        print(winner_msg)
        print(reason_msg)
        self._observer_info(winner_msg)
        self._observer_info(reason_msg)
        
        rounds_msg = f"\nGame lasted {self.game_state.round_number} rounds"
        print(rounds_msg)
        self._observer_info(rounds_msg.replace("\n", ""))
        
        final_status_msg = f"\nFinal Status:"
        print(final_status_msg)
        self._observer_info(final_status_msg.replace("\n", ""))
        
        for player in self.game_state.players:
            status = "ALIVE" if player.is_alive else "ELIMINATED"
            player_status = f"  {player.name} ({player.role.value}): {status}"
            print(player_status)
            self._observer_info(player_status)
        
        elimination_msg = f"\nElimination order: {' → '.join(self.game_state.elimination_history)}"
        print(elimination_msg)
        self._observer_info(elimination_msg.replace("\n", ""))
        
        # Create comprehensive end-game logging
        self._create_comprehensive_logs()
        
        return self.game_state.winner
    
    def _create_comprehensive_logs(self):
        """Create comprehensive end-game logging with all agent contexts and decisions"""
        # Use the existing session directory
        log_dir = self.game_log_dir
        
        try:
            # Observer log is already in the directory
            
            # Generate individual player state files
            for player in self.game_state.players:
                self._create_player_state_file(player, log_dir)
            
            # Create comprehensive game summary
            self._create_game_summary_file(log_dir)
            
            print(f"📁 Comprehensive logs created in folder: {log_dir}")
            self._observer_info(f"Comprehensive logs created in folder: {log_dir}")
            
        except Exception as e:
            print(f"❌ Error creating comprehensive logs: {e}")
            self._observer_info(f"Error creating comprehensive logs: {e}")
    
    def _create_player_state_file(self, player: Player, log_dir: str):
        """Create simple state file showing final context for this agent"""
        filename = f"{player.name.lower()}_final_context.txt"
        filepath = os.path.join(log_dir, filename)
        
        # Create a mock agent to get the context they would have seen
        agent = self._create_mock_agent(player)
        
        with open(filepath, 'w') as f:
            # Just write the raw final context, no extra formatting
            final_context = agent.get_base_context(self.game_state)
            f.write(final_context)
    
    def _create_mock_agent(self, player: Player):
        """Create a mock agent to generate context for this player"""
        if player.role == Role.MAFIA:
            from role_agents import MafiaAgent
            return MafiaAgent(player.name, player.personality, self.llm)
        elif player.role == Role.DOCTOR:
            from role_agents import DoctorAgent
            return DoctorAgent(player.name, player.personality, self.llm)
        elif player.role == Role.DETECTIVE:
            from role_agents import DetectiveAgent
            return DetectiveAgent(player.name, player.personality, self.llm)
        else:
            from role_agents import VillagerAgent
            return VillagerAgent(player.name, player.personality, self.llm)
    
    def _create_game_summary_file(self, log_dir: str):
        """Create comprehensive game summary with statistics"""
        filepath = os.path.join(log_dir, "game_summary.txt")
        
        with open(filepath, 'w') as f:
            f.write("=== MAFIA GAME COMPREHENSIVE SUMMARY ===\n\n")
            
            f.write(f"Game Configuration:\n")
            f.write(f"- Total Players: {len(self.game_state.players)}\n")
            f.write(f"- Mafia Count: {self.num_mafia}\n")
            f.write(f"- Max Discussion Rounds: {self.max_discussion_rounds}\n")
            f.write(f"- Model Used: {self.llm.model_name}\n\n")
            
            f.write(f"Game Outcome:\n")
            f.write(f"- Winner: {self.game_state.winner.upper()}\n")
            f.write(f"- Total Rounds: {self.game_state.round_number}\n")
            f.write(f"- Elimination Order: {' → '.join(self.game_state.elimination_history)}\n\n")
            
            f.write("Team Composition:\n")
            mafia_team = [p.name for p in self.game_state.players if p.role == Role.MAFIA]
            village_team = [p.name for p in self.game_state.players if p.role != Role.MAFIA]
            
            f.write(f"Mafia Team ({len(mafia_team)}): {', '.join(mafia_team)}\n")
            f.write(f"Village Team ({len(village_team)}): {', '.join(village_team)}\n\n")
            
            f.write("Final Status:\n")
            for player in self.game_state.players:
                status = "ALIVE" if player.is_alive else "ELIMINATED"
                f.write(f"- {player.name} ({player.role.value}): {status}\n")
            
            f.write("\n=== GAME ANALYSIS ===\n")
            f.write("Key Factors in Outcome:\n")
            
            # Analyze eliminations
            eliminated_mafia = [name for name in self.game_state.elimination_history 
                              if any(p.name == name and p.role == Role.MAFIA for p in self.game_state.players)]
            eliminated_village = [name for name in self.game_state.elimination_history 
                                if any(p.name == name and p.role != Role.MAFIA for p in self.game_state.players)]
            
            f.write(f"- Mafia eliminated: {len(eliminated_mafia)} ({', '.join(eliminated_mafia) if eliminated_mafia else 'None'})\n")
            f.write(f"- Village eliminated: {len(eliminated_village)} ({', '.join(eliminated_village) if eliminated_village else 'None'})\n")
            
            # Special roles impact
            detective_alive = any(p.is_alive and p.role == Role.DETECTIVE for p in self.game_state.players)
            doctor_alive = any(p.is_alive and p.role == Role.DOCTOR for p in self.game_state.players)
            
            f.write(f"- Detective survived: {detective_alive}\n")
            f.write(f"- Doctor survived: {doctor_alive}\n")
            
            if self.game_state.detective_results:
                f.write(f"- Detective investigations: {len(self.game_state.detective_results)} successful\n")
            
            f.write("\n=== PERSONALITY IMPACT ===\n")
            for player in self.game_state.players:
                if not player.is_alive:
                    elimination_round = self._get_elimination_round(player.name)
                    f.write(f"- {player.name}: {player.personality[:50]}... (Eliminated round {elimination_round})\n")
                else:
                    f.write(f"- {player.name}: {player.personality[:50]}... (Survived)\n")
    
    def _get_elimination_round(self, player_name: str) -> int:
        """Get the round when a player was eliminated"""
        if player_name in self.game_state.elimination_history:
            # Since we have 1 elimination per round, the position in history + 1 is the round
            return self.game_state.elimination_history.index(player_name) + 1
        return 0
    
    def _get_player_voting_history(self, player_name: str) -> Dict[int, str]:
        """Get voting history for a specific player"""
        # This is a simplified version - in a full implementation, 
        # we would track voting history per round
        # For now, we'll return empty dict as this would require 
        # more extensive tracking during the game
        return {}
    
    def _track_player_night_action(self, player_name: str, action_type: str, target: str, reason: str):
        """Track individual player's night action"""
        if player_name not in self.game_state.player_night_actions:
            self.game_state.player_night_actions[player_name] = []
        
        action_record = {
            'round': self.game_state.round_number,
            'action_type': action_type,
            'target': target,
            'reason': reason
        }
        self.game_state.player_night_actions[player_name].append(action_record)
    
    def _log_agent_context(self, agent_name: str, context: str, phase_description: str):
        """Log the context being passed to an agent for debugging"""
        # Check if intermediate context logging is enabled
        if not self.log_intermediate_contexts:
            return
            
        if not hasattr(self, 'context_log_dir'):
            return
            
        # Only log for alive players
        if agent_name not in self.game_state.alive_players:
            return
            
        context_file = os.path.join(self.context_log_dir, f"{agent_name.lower()}_context.txt")
        
        with open(context_file, 'a') as f:
            f.write(f"=== {phase_description} ===\n")
            f.write(context)
            f.write(f"\n{'-' * 50}\n\n")
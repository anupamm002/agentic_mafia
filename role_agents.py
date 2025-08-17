from typing import Dict, List, Optional
from base_agent import BaseAgent
from game_state import GameState, Role, GamePhase
from structured_responses import NightDecision, DiscussionResponse, VoteDecision, DefenseResponse

class MafiaAgent(BaseAgent):
    def __init__(self, name: str, personality: str, llm_interface):
        super().__init__(name, personality, Role.MAFIA, llm_interface)
    
    def make_night_decision(self, game_state: GameState) -> Optional[Dict]:
        alive_non_mafia = [p.name for p in game_state.get_alive_players() 
                          if p.role != Role.MAFIA]
        
        if not alive_non_mafia:
            return None
        
        prompt = f"""{self.get_base_context(game_state)}

NIGHT PHASE - MAFIA ELIMINATION DECISION

You must choose someone to eliminate tonight. Consider:
- Who poses the biggest threat to the Mafia?
- Who might be the Doctor or Detective?
- What would be the most strategic elimination?

Available targets: {', '.join(alive_non_mafia)}

Respond with JSON format:
{{
    "target": "player_name",
    "reason": "brief explanation for your choice"
}}"""

        response = self.llm.generate_json_response(prompt)
        return response

    def participate_in_discussion(self, game_state: GameState) -> Optional[DiscussionResponse]:
        if game_state.phase not in [GamePhase.DAY_DISCUSSION]:
            return None
        
        # Check if being mentioned or attacked recently
        recent_messages = game_state.discussion_messages[-5:] if game_state.discussion_messages else []
        being_attacked = any(self.name.lower() in msg.message.lower() and 
                           any(word in msg.message.lower() for word in ['suspicious', 'sus', 'mafia', 'vote', 'eliminate'])
                           for msg in recent_messages)
        
        urgency = 5 if being_attacked else 3  # High urgency if being attacked
        
        prompt = f"""{self.get_base_context(game_state)}

DAY DISCUSSION PHASE

As a Mafia member, you need to:
- Deflect suspicion from yourself and other Mafia
- Build suspicion against Village members
- Appear helpful and trustworthy
{'- IMPORTANT: You are being accused/suspected! Defend yourself!' if being_attacked else ''}

Do you want to speak in this round? If yes, what will you say? Be strategic but natural.
Keep your response under 100 words.
Urgency (1-5): {urgency} - higher if you need to defend yourself or respond to someone"""

        response = self.llm.generate_structured_response(prompt, DiscussionResponse)
        return response

    def vote(self, game_state: GameState, candidates: List[str]) -> Dict[str, str]:
        from structured_responses import VoteDecision
        
        prompt = f"""{self.get_base_context(game_state)}

VOTING PHASE

You must vote to eliminate ONE of these candidates: {', '.join(candidates)}
NOTE: You cannot vote for yourself - only choose from the candidates listed above.

Voting history so far:
{self._format_voting_history(game_state)}

As a Mafia member, vote strategically to eliminate Village members or deflect suspicion.
Choose your target and provide a clear reason for your vote."""

        vote_decision = self.llm.generate_structured_response(prompt, VoteDecision)
        
        # Validate target is in candidates
        if vote_decision.target not in candidates:
            # Find closest match
            target = candidates[0]
            for candidate in candidates:
                if candidate.lower() in vote_decision.target.lower():
                    target = candidate
                    break
            vote_decision.target = target
        
        return {"target": vote_decision.target, "reason": vote_decision.reason}

    def defend_self(self, game_state: GameState) -> str:
        prompt = f"""{self.get_base_context(game_state)}

DEFENSE PHASE

You are being voted for elimination! Make a defense to convince others of your innocence.
Be convincing but not too desperate. Use your personality and any evidence that supports you.

Respond with your defense (under 150 words)."""

        return self.llm.generate_response(prompt)


    def _format_voting_history(self, game_state: GameState) -> str:
        if not game_state.votes:
            return "No votes cast yet."
        
        vote_summary = ""
        for voter, target in game_state.votes.items():
            vote_summary += f"{voter} voted for {target}\n"
        return vote_summary

class DoctorAgent(BaseAgent):
    def __init__(self, name: str, personality: str, llm_interface):
        super().__init__(name, personality, Role.DOCTOR, llm_interface)
    
    def make_night_decision(self, game_state: GameState) -> Optional[Dict]:
        alive_players = [p.name for p in game_state.get_alive_players() if p.name != self.name]
        
        if not alive_players:
            return None
        
        prompt = f"""{self.get_base_context(game_state)}

NIGHT PHASE - DOCTOR SAVE DECISION

You must choose someone to save tonight. Consider:
- Who is most likely to be targeted by Mafia?
- Who is most valuable to keep alive?
- You can save yourself if you have no better clue

Available targets: {', '.join(alive_players)}

Respond with JSON format:
{{
    "target": "player_name",
    "reason": "brief explanation for your choice"
}}"""

        response = self.llm.generate_json_response(prompt)
        return response

    def participate_in_discussion(self, game_state: GameState) -> Optional[DiscussionResponse]:
        if game_state.phase != GamePhase.DAY_DISCUSSION:
            return None
        
        # Check if being mentioned or attacked recently
        recent_messages = game_state.discussion_messages[-5:] if game_state.discussion_messages else []
        being_attacked = any(self.name.lower() in msg.message.lower() and 
                           any(word in msg.message.lower() for word in ['suspicious', 'sus', 'mafia', 'vote', 'eliminate'])
                           for msg in recent_messages)
        
        urgency = 5 if being_attacked else 2  # Doctors are usually more cautious
        
        prompt = f"""{self.get_base_context(game_state)}

DAY DISCUSSION PHASE

As the Doctor, be helpful in finding Mafia but don't reveal your role.
Share your thoughts on who might be suspicious.
{'- IMPORTANT: You are being accused/suspected! Defend yourself!' if being_attacked else ''}

Do you want to speak? If yes, what will you say?
Keep response under 100 words.
Urgency (1-5): {urgency}"""

        response = self.llm.generate_structured_response(prompt, DiscussionResponse)
        return response

    def vote(self, game_state: GameState, candidates: List[str]) -> Dict[str, str]:
        from structured_responses import VoteDecision
        
        prompt = f"""{self.get_base_context(game_state)}

VOTING PHASE

Vote to eliminate ONE of these candidates: {', '.join(candidates)}
NOTE: You cannot vote for yourself - only choose from the candidates listed above.

Voting so far:
{self._format_voting_history(game_state)}

As the Doctor, vote for who you think is most likely to be Mafia.
Choose your target and provide a clear reason for your vote."""

        vote_decision = self.llm.generate_structured_response(prompt, VoteDecision)
        
        # Validate target is in candidates
        if vote_decision.target not in candidates:
            target = candidates[0]
            for candidate in candidates:
                if candidate.lower() in vote_decision.target.lower():
                    target = candidate
                    break
            vote_decision.target = target
        
        return {"target": vote_decision.target, "reason": vote_decision.reason}

    def defend_self(self, game_state: GameState) -> str:
        prompt = f"""{self.get_base_context(game_state)}

DEFENSE PHASE

You're being voted for elimination! Defend yourself without revealing you're the Doctor.

Respond with your defense (under 150 words)."""

        return self.llm.generate_response(prompt)


    def _format_voting_history(self, game_state: GameState) -> str:
        if not game_state.votes:
            return "No votes cast yet."
        vote_summary = ""
        for voter, target in game_state.votes.items():
            vote_summary += f"{voter} voted for {target}\n"
        return vote_summary

class DetectiveAgent(BaseAgent):
    def __init__(self, name: str, personality: str, llm_interface):
        super().__init__(name, personality, Role.DETECTIVE, llm_interface)
    
    def make_night_decision(self, game_state: GameState) -> Optional[Dict]:
        alive_players = [p.name for p in game_state.get_alive_players() if p.name != self.name]
        uninvestigated = [name for name in alive_players 
                         if name not in game_state.detective_results]
        
        if not uninvestigated:
            return None
        
        prompt = f"""{self.get_base_context(game_state)}

NIGHT PHASE - DETECTIVE INVESTIGATION

Choose someone to investigate tonight. You will learn their exact role.
Consider who you're most suspicious of or who would give you the most information.

Available targets: {', '.join(uninvestigated)}

Respond with JSON format:
{{
    "target": "player_name",
    "reason": "brief explanation for your choice"
}}"""

        response = self.llm.generate_json_response(prompt)
        return response

    def participate_in_discussion(self, game_state: GameState) -> Optional[DiscussionResponse]:
        if game_state.phase != GamePhase.DAY_DISCUSSION:
            return None
        
        # Check if being mentioned or attacked recently
        recent_messages = game_state.discussion_messages[-5:] if game_state.discussion_messages else []
        being_attacked = any(self.name.lower() in msg.message.lower() and 
                           any(word in msg.message.lower() for word in ['suspicious', 'sus', 'mafia', 'vote', 'eliminate'])
                           for msg in recent_messages)
        
        urgency = 5 if being_attacked else 4  # Detectives often have important info
        
        prompt = f"""{self.get_base_context(game_state)}

DAY DISCUSSION PHASE

As the Detective, you have investigation results but must be strategic about revealing them.
Consider sharing information that helps eliminate Mafia without making yourself a target.
{'- IMPORTANT: You are being accused/suspected! Defend yourself!' if being_attacked else ''}

Do you want to speak? If yes, what will you say?
Keep response under 100 words.
Urgency (1-5): {urgency}"""

        response = self.llm.generate_structured_response(prompt, DiscussionResponse)
        return response

    def vote(self, game_state: GameState, candidates: List[str]) -> Dict[str, str]:
        from structured_responses import VoteDecision
        
        prompt = f"""{self.get_base_context(game_state)}

VOTING PHASE

Vote to eliminate ONE of these candidates: {', '.join(candidates)}
NOTE: You cannot vote for yourself - only choose from the candidates listed above.

As the Detective, use your investigation results to vote strategically.
You may choose to reveal your findings or keep them secret.
Choose your target and provide a clear reason for your vote."""

        vote_decision = self.llm.generate_structured_response(prompt, VoteDecision)
        
        # Validate target is in candidates
        if vote_decision.target not in candidates:
            target = candidates[0]
            for candidate in candidates:
                if candidate.lower() in vote_decision.target.lower():
                    target = candidate
                    break
            vote_decision.target = target
        
        return {"target": vote_decision.target, "reason": vote_decision.reason}

    def defend_self(self, game_state: GameState) -> str:
        prompt = f"""{self.get_base_context(game_state)}

DEFENSE PHASE

You're being voted for elimination! Consider if you should reveal your Detective role and findings.

Respond with your defense (under 150 words)."""

        return self.llm.generate_response(prompt)


    def _format_voting_history(self, game_state: GameState) -> str:
        if not game_state.votes:
            return "No votes cast yet."
        vote_summary = ""
        for voter, target in game_state.votes.items():
            vote_summary += f"{voter} voted for {target}\n"
        return vote_summary

class VillagerAgent(BaseAgent):
    def __init__(self, name: str, personality: str, llm_interface):
        super().__init__(name, personality, Role.VILLAGER, llm_interface)
    
    def make_night_decision(self, game_state: GameState) -> Optional[Dict]:
        return None  # Villagers have no night action

    def participate_in_discussion(self, game_state: GameState) -> Optional[DiscussionResponse]:
        if game_state.phase != GamePhase.DAY_DISCUSSION:
            return None
        
        # Check if being mentioned or attacked recently
        recent_messages = game_state.discussion_messages[-5:] if game_state.discussion_messages else []
        being_attacked = any(self.name.lower() in msg.message.lower() and 
                           any(word in msg.message.lower() for word in ['suspicious', 'sus', 'mafia', 'vote', 'eliminate'])
                           for msg in recent_messages)
        
        urgency = 5 if being_attacked else 3  # Normal urgency for villagers
        
        prompt = f"""{self.get_base_context(game_state)}

DAY DISCUSSION PHASE

As a Villager, share your thoughts on who might be Mafia based on their behavior and voting patterns.
{'- IMPORTANT: You are being accused/suspected! Defend yourself!' if being_attacked else ''}

Do you want to speak? If yes, what will you say?
Keep response under 100 words.
Urgency (1-5): {urgency}"""

        response = self.llm.generate_structured_response(prompt, DiscussionResponse)
        return response

    def vote(self, game_state: GameState, candidates: List[str]) -> Dict[str, str]:
        from structured_responses import VoteDecision
        
        prompt = f"""{self.get_base_context(game_state)}

VOTING PHASE

Vote to eliminate ONE of these candidates: {', '.join(candidates)}
NOTE: You cannot vote for yourself - only choose from the candidates listed above.

Voting so far:
{self._format_voting_history(game_state)}

As a Villager, vote for who you think is most likely to be Mafia based on behavior and discussion.
Choose your target and provide a clear reason for your vote."""

        vote_decision = self.llm.generate_structured_response(prompt, VoteDecision)
        
        # Validate target is in candidates
        if vote_decision.target not in candidates:
            target = candidates[0]
            for candidate in candidates:
                if candidate.lower() in vote_decision.target.lower():
                    target = candidate
                    break
            vote_decision.target = target
        
        return {"target": vote_decision.target, "reason": vote_decision.reason}

    def defend_self(self, game_state: GameState) -> str:
        prompt = f"""{self.get_base_context(game_state)}

DEFENSE PHASE

You're being voted for elimination! Make your case for why you're innocent.

Respond with your defense (under 150 words)."""

        return self.llm.generate_response(prompt)


    def _format_voting_history(self, game_state: GameState) -> str:
        if not game_state.votes:
            return "No votes cast yet."
        vote_summary = ""
        for voter, target in game_state.votes.items():
            vote_summary += f"{voter} voted for {target}\n"
        return vote_summary
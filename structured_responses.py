from dataclasses import dataclass
from typing import Optional


@dataclass
class NightDecision:
    target: str
    reason: str


@dataclass
class DiscussionResponse:
    speak: bool
    comment: str
    urgency: int  # 1-5, higher means wants to speak sooner (e.g., to defend)


@dataclass
class VoteDecision:
    target: str
    reason: str


@dataclass
class DefenseResponse:
    defense: str
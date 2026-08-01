from dataclasses import dataclass


@dataclass
class RateResult:
    rating: float = 0.0
    rating_count: int = 0


@dataclass
class VoteCommentResult:
    comment_id: int = 0
    comment_score: int = 0
    comment_vote: int = 0

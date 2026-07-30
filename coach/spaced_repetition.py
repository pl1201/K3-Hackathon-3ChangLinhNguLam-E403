"""Spaced Repetition scheduling using the FSRS algorithm.

Calculates the next review date for a topic/question based on whether
the user answered correctly or incorrectly.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

# Import FSRS classes
from fsrs import Scheduler, Card, Rating, State

from coach.schemas_spaced_repetition import SpacedRepetitionResult

logger = logging.getLogger(__name__)

def schedule_next_review(is_correct: bool, previous_card_json: Optional[str] = None) -> SpacedRepetitionResult:
    """Calculate the next review schedule for a quiz question using FSRS.
    
    Args:
        is_correct: True if the user answered correctly, False otherwise.
        previous_card_json: The JSON string of the FSRS Card state from the database.
                            If None, assumes this is the first time the user saw this question.
                            
    Returns:
        SpacedRepetitionResult containing the new schedule.
    """
    scheduler = Scheduler()
    
    # Restore previous state if it exists
    if previous_card_json:
        try:
            card = Card.from_json(previous_card_json)
        except Exception as e:
            logger.warning(f"Failed to parse previous_card_json. Starting fresh. Error: {e}")
            card = Card()
    else:
        card = Card()
            
    # Apply rating: 
    # If correct, we rate it 'Good' (standard retention).
    # If incorrect, we rate it 'Again' (forgotten).
    rating = Rating.Good if is_correct else Rating.Again
    
    # Update card
    now = datetime.now(timezone.utc)
    card, review_log = scheduler.review_card(card, rating, now)
    
    # Calculate scheduled days
    if card.last_review and card.due:
        scheduled_days = (card.due - card.last_review).total_seconds() / 86400.0
    else:
        scheduled_days = 0.0
    
    return SpacedRepetitionResult(
        is_correct=is_correct,
        scheduled_days=scheduled_days,
        next_review_iso=card.due.isoformat() if card.due else "",
        card_state_json=card.to_json()
    )

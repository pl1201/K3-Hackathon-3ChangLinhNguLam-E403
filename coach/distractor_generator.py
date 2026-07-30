"""Distractor Generation using YAKE.

Extracts domain-specific keywords from text to be used as plausible
distractors (wrong answers) in multiple-choice questions using a lightweight
NLP algorithm.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


def extract_distractors(context_text: str, correct_answer: str, top_n: int = 5) -> List[str]:
    """Extract keywords related to the context to serve as distractors.

    Args:
        context_text: The source text (e.g. a paragraph or chapter).
        correct_answer: The correct answer (so we can exclude it).
        top_n: Number of distractors to extract.

    Returns:
        List of extracted keywords (strings).
    """
    try:
        import yake
    except ImportError:
        raise RuntimeError("yake is not installed. Please install it to use distractor generation.")

    # Yake configuration
    language = "vi" # Works well with English and Vietnamese text natively without models
    max_ngram_size = 3
    deduplication_threshold = 0.7 # Less strict to allow more keywords on short text
    numOfKeywords = top_n + 5 # Request more in case we filter some out
    
    custom_kw_extractor = yake.KeywordExtractor(
        lan=language, 
        n=max_ngram_size, 
        dedupLim=deduplication_threshold, 
        top=numOfKeywords, 
        features=None
    )
    
    keywords = custom_kw_extractor.extract_keywords(context_text)
    
    distractors = []
    correct_lower = correct_answer.lower().strip()
    
    for kw, score in keywords: # Yake returns (keyword, score) where lower score is better
        kw_lower = kw.lower().strip()
        # Filter out the correct answer or partial matches to avoid confusing the student
        if kw_lower != correct_lower and kw_lower not in correct_lower and correct_lower not in kw_lower:
            distractors.append(kw)
        
        if len(distractors) >= top_n:
            break
            
    return distractors


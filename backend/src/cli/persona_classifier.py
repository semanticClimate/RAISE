"""
RAISE — Persona Intent Classifier & Dynamic Entity Memory
=========================================================
Distinguishes conversational utterances (greetings, name updates, identity recall)
from factual academic queries with guardrails protecting domain terminology.
"""

from __future__ import annotations

import re
from typing import Any, Dict

NON_NAME_TOKENS = {
    # Question words & interrogative helpers
    "what", "whats", "what's", "who", "whos", "who's", "how", "why", "where", "when", "which",
    # Conjunctions, prepositions, pronouns
    "and", "or", "but", "if", "then", "so", "as", "at", "by", "for", "with", "about", "against",
    "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "yours", "your", "mine", "my", "our", "ours", "their", "theirs", "his", "her", "hers", "its", "it",
    "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    # Conversational particles & auxiliaries
    "please", "tell", "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "here", "there", "just", "also", "now", "today", "again", "too", "very",
    # Articles, generic roles & common adjectives
    "a", "an", "the", "someone", "anyone", "everyone", "nobody", "somebody", "anybody", "everybody",
    "person", "human", "user", "student", "researcher", "engineer", "scientist", "professor", "doctor",
    "busy", "ready", "new", "fine", "good", "great", "well", "okay", "ok", "looking", "asking", "wondering",
    "instead", "actually", "right",
    # Salutations to prevent misclassification
    "hi", "hello", "hey", "hola", "sup", "yo", "greetings",
}

DOMAIN_FACTUAL_TERMS = {
    "iit", "iitm", "campus", "located", "location", "acres", "annual report", "dhanbad",
    "director", "nominee", "nominees", "governor", "board", "faculty", "student", "students",
    "ranking", "nirf", "grant", "revenue", "budget", "expenditure", "deemed", "university",
    "ugc", "act", "established", "founded", "history", "table", "section", "page",
}


def extract_conversational_persona(text: str) -> Dict[str, Any]:
    """
    Generalized conversational intent classifier and dynamic entity extractor.
    Enforces strict guardrails against false conversational classification:
    - Queries containing question marks, interrogatives, or academic entities are NEVER classified as intros
    - Possessive pronouns ('its') are strictly excluded from intro patterns
    - Name intros require explicit, anchored introduction syntax
    """
    clean_text = text.strip()
    t_lower = clean_text.lower()

    # Research / Factual Query Guardrail:
    interrogative_words = {
        "where", "how", "what", "when", "why", "which", "who", "whom", "whose",
        "is", "are", "was", "were", "does", "did", "do", "can", "could", "would", "should",
    }
    has_question_mark = "?" in clean_text
    first_word = t_lower.split()[0].strip(",.:;!?") if t_lower.split() else ""
    has_interrogative_start = first_word in interrogative_words

    has_domain_term = any(re.search(rf"\b{re.escape(term)}\b", t_lower) for term in DOMAIN_FACTUAL_TERMS)

    # If it is clearly an inquiry, immediately return research_query
    if (has_question_mark or has_interrogative_start or has_domain_term) and not any(
        p in t_lower
        for p in [
            "your name", "who are you", "who am i", "what is my name", "what's my name",
            "what can you do", "who made you", "introduce yourself", "tell me about yourself",
        ]
    ):
        return {"type": "research_query"}

    # User introductions & name update patterns (Strictly anchored, NO possessive 'its')
    intro_patterns = [
        r"(?i)^(?:hi\s*[,!]?\s*|hello\s*[,!]?\s*|hey\s*[,!]?\s*)?(?:change\s+(?:my\s+)?name\s+to|update\s+(?:my\s+)?name\s+to|set\s+(?:my\s+)?name\s+to)\s+([A-Za-z\s'’]+)\s*[\.!]?$",
        r"(?i)^(?:hi\s*[,!]?\s*|hello\s*[,!]?\s*|hey\s*[,!]?\s*)?(?:actually\s+(?:my\s+name\s+is|i\s+am|i'm|call\s+me))\s+([A-Za-z\s'’]+)\s*[\.!]?$",
        r"(?i)^(?:hi\s*[,!]?\s*|hello\s*[,!]?\s*|hey\s*[,!]?\s*)?(?:call\s+me\s+instead)\s+([A-Za-z\s'’]+)\s*[\.!]?$",
        r"(?i)^(?:hi\s*[,!]?\s*|hello\s*[,!]?\s*|hey\s*[,!]?\s*)?(?:my\s+name\s+is(?:\s+now)?|call\s+me)\s+([A-Za-z\s'’]+)\s*[\.!]?$",
        r"(?i)^(?:hi\s*[,!]?\s*|hello\s*[,!]?\s*|hey\s*[,!]?\s*)?(?:i\s+am|i'm|this\s+is)\s+([A-Za-z\s'’]+)\s*[\.!]?$",
    ]

    for pat in intro_patterns:
        m = re.match(pat, clean_text)
        if m:
            raw_match = m.group(1).strip()
            tokens = [re.sub(r"[^\w]", "", w) for w in raw_match.split()]
            name_tokens = []
            for token in tokens:
                if not token:
                    continue
                if token.lower() in NON_NAME_TOKENS or token.lower() in DOMAIN_FACTUAL_TERMS:
                    if name_tokens:
                        break
                    continue
                name_tokens.append(token.title())
                if len(name_tokens) >= 3:
                    break

            if name_tokens and len(name_tokens) <= 3:
                extracted_name = " ".join(name_tokens)
                return {"type": "name_intro", "name": extracted_name}

    # User identity recall inquiries
    recall_phrases = [
        "know my name", "what is my name", "what's my name", "who am i",
        "remember my name", "recall my name", "remember me", "know who i am",
    ]
    if any(p in t_lower for p in recall_phrases):
        return {"type": "name_recall"}

    # Assistant identity & capability inquiries
    bot_identity_phrases = [
        "your name", "who are you", "what are you", "what is yours", "what's yours",
        "who made you", "what can you do", "introduce yourself",
        "tell me about yourself", "give your name", "tell your name",
    ]
    if any(p in t_lower for p in bot_identity_phrases):
        return {"type": "bot_identity"}

    # Natural greetings & conversational openers (Must be standalone greetings)
    greeting_typo_regex = re.compile(
        r"^(hi+|hello+|helo+|hekko+|hey+|heyy+|heyo|howdy|hola|yo+|sup|hlo|hlw|greetings)(?:\s+there|\s+raise|\s+bot|\s*!|\s*\.|\s*\?)*$",
        re.IGNORECASE
    )
    greeting_words = {
        "hi", "hello", "helo", "hekko", "hey", "heyy", "he", "hola", "howdy", "sup", "yo",
        "hlo", "hlw", "greetings", "good morning", "good afternoon", "good evening", "good day",
    }
    if t_lower in greeting_words or greeting_typo_regex.match(text.strip()):
        return {"type": "greeting"}

    return {"type": "research_query"}

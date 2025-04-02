#!/usr/bin/env python3
"""Data for the author command."""

import random

# Griffin's facts and achievements (funny and entertaining)
GRIFFIN_FACTS = [
    "Once debugged an entire codebase just by staring at it intensely.",
    "Wrote a recursive algorithm that somehow returns before it's called.",
    "Speaks fluent Python, JavaScript, and Hexadecimal.",
    "Git commits actually commit to him.",
    "His code compiles so fast that time occasionally runs backward.",
    "Invented a new sorting algorithm that's O(whatever he feels like).",
    "Has never encountered a bug - only 'unexpected features'.",
    "Wrote his first 'Hello World' program before he was born.",
    "Stackoverflow moderators ask him questions.",
    "Uses binary as a meditation technique.",
    "Makes GPT models question their existence.",
    "Has a pet rubber duck that actually suggests useful solutions.",
    "His IDEs automatically refactor code when he enters the room.",
    "Doesn't need comments; his code is self-explanatory to the universe.",
    "The cloud is just a metaphor for where his code gracefully floats.",
]

# Griffin's quotes (wise programming advice)
GRIFFIN_QUOTES = [
    "You can run from your past but you're just going to sprint headfirst into your future.",
    "Do not tell people your insecurities, they will just use them against you.",
    "Sometimes I'm spitballing and I spit gold.",
    "I'm tall enough for things to not go over my head. Usually they just hit it.",
]

# Griffin's daily advice
DAILY_ADVICE = [
    "Take a walk outside. Nature has the best algorithms.",
    "Hydrate! Dehydrated programmers make dry code.",
    "Comment your code as if the next developer is a psychopath who knows where you live.",
    "Backup your data. Then backup your backup.",
    "Write tests first, code later. Or just wing it, I'm not your boss.",
    "When all else fails, try turning it off and on again.",
]

# Smaller ASCII art for Griffin logo (to fit smaller terminals)
GRIFFIN_LOGO = r"""
  _____       _  __  __ _       
 / ____|     (_)/ _|/ _(_)      
| |  __ _ __ _| |_| |_ _ _ __   
| | |_ | '__| |  _|  _| | '_ \  
| |__| | |  | | | | | | | | | | 
 \_____|_|  |_|_| |_| |_|_| |_| 
 The Programming God
"""

# Smaller ASCII art for "GOD MODE" text
GOD_MODE_TEXT = r"""
  ____  ____  ____    __  __  ____  ____  ____ 
 / ___||  _ \|  _ \  |  \/  ||  _ \|  _ \| ___|
| |  _ | |_) | | | | | |\/| || | | | | | |___ \
| |_| ||  _ <| |_| | | |  | || |_| | |_| |___) |
 \____||_| \_\____/  |_|  |_||____/|____/|____/ 
"""

# Smaller ASCII art for "SEIZE MODE" text
SEIZE_MODE_TEXT = r"""
 ____  _____ ___ _________ _   _ ____  _____   __  __  ___  ____  _____ 
/ ___|| ____|_ _|__  / ___| | | |  _ \| ____| |  \/  |/ _ \|  _ \| ____|
\___ \|  _|  | |  / /|___ \ | | | |_) |  _|   | |\/| | | | | | | |  _|  
 ___) | |___ | | / /  ___) | |_| |  _ <| |___  | |  | | |_| | |_| | |___ 
|____/|_____|___/____|____/ \___/|_| \_\_____|_|  |_|\___/|____/|_____|
"""


def get_random_facts(count: int = 3) -> list[str]:
    """Get a list of random fun facts about Griffin.

    Args:
        count: Number of facts to return

    Returns:
        List of random facts
    """
    return random.sample(GRIFFIN_FACTS, min(count, len(GRIFFIN_FACTS)))


def get_random_quote() -> str:
    """Get a random programming quote from Griffin.

    Returns:
        A random quote
    """
    return random.choice(GRIFFIN_QUOTES)


def get_random_advice() -> str:
    """Get a random piece of programming advice from Griffin.

    Returns:
        A random piece of advice
    """
    return random.choice(DAILY_ADVICE)

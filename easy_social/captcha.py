from __future__ import annotations

import random

from flask import current_app, session

BYPASS_TOKEN = "bypass"


def generate_captcha() -> tuple[str, int]:
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    question = f"What is {a} + {b}?"
    answer = a + b
    session["captcha_answer"] = answer
    return question, answer


def validate_captcha(user_input: str) -> bool:
    if current_app.config.get("TESTING") and user_input == BYPASS_TOKEN:
        session.pop("captcha_answer", None)
        return True
    expected = session.pop("captcha_answer", None)
    if expected is None:
        return False
    try:
        return int(user_input) == expected
    except (ValueError, TypeError):
        return False

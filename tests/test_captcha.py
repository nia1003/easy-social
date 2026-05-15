from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_generate_captcha_returns_addition_question_and_stores_answer(app):
    with app.test_request_context():
        from flask import session
        from easy_social.captcha import generate_captcha
        question, answer = generate_captcha()
        assert "+" in question
        assert isinstance(answer, int)
        assert 2 <= answer <= 18
        assert session["captcha_answer"] == answer


def test_validate_captcha_correct_answer(app):
    with app.test_request_context():
        from flask import session
        from easy_social.captcha import validate_captcha
        session["captcha_answer"] = 7
        assert validate_captcha("7") is True
        assert "captcha_answer" not in session


def test_validate_captcha_wrong_answer(app):
    with app.test_request_context():
        from flask import session
        from easy_social.captcha import validate_captcha
        session["captcha_answer"] = 7
        assert validate_captcha("5") is False


def test_validate_captcha_non_numeric_input(app):
    with app.test_request_context():
        from flask import session
        from easy_social.captcha import validate_captcha
        session["captcha_answer"] = 7
        assert validate_captcha("abc") is False


def test_validate_captcha_missing_session_answer(app):
    with app.test_request_context():
        from easy_social.captcha import validate_captcha
        assert validate_captcha("5") is False


def test_validate_captcha_bypass_in_testing_mode(app):
    with app.test_request_context():
        from flask import session
        from easy_social.captcha import validate_captcha
        session["captcha_answer"] = 7
        assert validate_captcha("bypass") is True


def test_captcha_answer_consumed_after_correct_validation(app):
    with app.test_request_context():
        from flask import session
        from easy_social.captcha import validate_captcha
        session["captcha_answer"] = 5
        validate_captcha("5")
        assert "captcha_answer" not in session

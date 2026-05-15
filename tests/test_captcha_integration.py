from __future__ import annotations

import pytest

from easy_social.models import User

from conftest import login, register

pytestmark = pytest.mark.integration


def test_register_page_includes_captcha_question(client):
    response = client.get("/auth/register")
    assert response.status_code == 200
    assert b"CAPTCHA" in response.data
    assert b"What is" in response.data


def test_register_succeeds_with_correct_captcha(client, app):
    with client.session_transaction() as sess:
        sess["captcha_answer"] = 8
    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha": "8",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Feed" in response.data
    with app.app_context():
        assert User.query.filter_by(username="alice").first() is not None


def test_register_fails_with_wrong_captcha(client, app):
    with client.session_transaction() as sess:
        sess["captcha_answer"] = 8
    response = client.post(
        "/auth/register",
        data={
            "username": "bob",
            "email": "bob@example.com",
            "password": "password",
            "captcha": "99",
        },
        follow_redirects=True,
    )
    assert b"Incorrect CAPTCHA" in response.data
    with app.app_context():
        assert User.query.filter_by(username="bob").first() is None


def test_register_fails_with_missing_captcha(client, app):
    with client.session_transaction() as sess:
        sess["captcha_answer"] = 8
    response = client.post(
        "/auth/register",
        data={
            "username": "charlie",
            "email": "charlie@example.com",
            "password": "password",
            "captcha": "",
        },
        follow_redirects=True,
    )
    assert b"Incorrect CAPTCHA" in response.data
    with app.app_context():
        assert User.query.filter_by(username="charlie").first() is None


def test_captcha_bypass_works_in_testing_mode(client, app):
    response = register(client, "dave")
    assert b"Feed" in response.data
    with app.app_context():
        assert User.query.filter_by(username="dave").first() is not None


def test_captcha_refreshed_after_failed_attempt(client):
    with client.session_transaction() as sess:
        sess["captcha_answer"] = 8
    response = client.post(
        "/auth/register",
        data={
            "username": "eve",
            "email": "eve@example.com",
            "password": "password",
            "captcha": "99",
        },
        follow_redirects=True,
    )
    assert b"What is" in response.data

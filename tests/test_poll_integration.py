from __future__ import annotations

import pytest

from easy_social.extensions import db
from easy_social.models import Poll, PollOption, PollVote, Post, User

from conftest import login, logout, register

pytestmark = pytest.mark.integration


def test_create_poll_post(client, app):
    register(client, "alice")
    response = client.post(
        "/polls",
        data={
            "body": "Favourite season?",
            "option_1": "Spring",
            "option_2": "Summer",
            "option_3": "Autumn",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Favourite season?" in response.data
    with app.app_context():
        post = Post.query.filter_by(body="Favourite season?").first()
        assert post is not None
        assert post.is_poll is True
        assert post.poll is not None
        assert len(post.poll.options) == 3


def test_create_poll_requires_body(client):
    register(client, "alice")
    response = client.post(
        "/polls",
        data={"body": "", "option_1": "Yes", "option_2": "No"},
        follow_redirects=True,
    )
    assert b"question" in response.data.lower() or b"required" in response.data.lower()


def test_create_poll_requires_at_least_two_options(client):
    register(client, "alice")
    response = client.post(
        "/polls",
        data={"body": "Question?", "option_1": "Only one"},
        follow_redirects=True,
    )
    assert b"at least 2" in response.data


def test_vote_on_poll(client, app):
    register(client, "alice")
    client.post(
        "/polls",
        data={"body": "Tea or coffee?", "option_1": "Tea", "option_2": "Coffee"},
        follow_redirects=True,
    )
    with app.app_context():
        poll = Poll.query.first()
        option_id = poll.options[0].id
        poll_id = poll.id

    response = client.post(
        f"/polls/{poll_id}/vote",
        data={"option_id": option_id},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        vote = PollVote.query.filter_by(option_id=option_id).first()
        assert vote is not None


def test_cannot_vote_twice(client, app):
    register(client, "alice")
    client.post(
        "/polls",
        data={"body": "Once only?", "option_1": "Yes", "option_2": "No"},
        follow_redirects=True,
    )
    with app.app_context():
        poll = Poll.query.first()
        option_id = poll.options[0].id
        poll_id = poll.id

    client.post(f"/polls/{poll_id}/vote", data={"option_id": option_id}, follow_redirects=True)
    response = client.post(
        f"/polls/{poll_id}/vote",
        data={"option_id": option_id},
        follow_redirects=True,
    )
    assert b"already voted" in response.data
    with app.app_context():
        assert PollVote.query.count() == 1


def test_poll_results_shown_after_voting(client, app):
    register(client, "alice")
    client.post(
        "/polls",
        data={"body": "Best pet?", "option_1": "Cat", "option_2": "Dog"},
        follow_redirects=True,
    )
    with app.app_context():
        poll = Poll.query.first()
        option_id = poll.options[0].id
        poll_id = poll.id

    response = client.post(
        f"/polls/{poll_id}/vote",
        data={"option_id": option_id},
        follow_redirects=True,
    )
    assert b"100.0%" in response.data or b"%" in response.data


def test_poll_with_no_option_id_shows_error(client, app):
    register(client, "alice")
    client.post(
        "/polls",
        data={"body": "Which?", "option_1": "A", "option_2": "B"},
        follow_redirects=True,
    )
    with app.app_context():
        poll_id = Poll.query.first().id

    response = client.post(
        f"/polls/{poll_id}/vote",
        data={},
        follow_redirects=True,
    )
    assert b"select an option" in response.data

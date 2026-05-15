from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from easy_social.extensions import db
from easy_social.models import Poll, PollOption, PollVote, Post, User

pytestmark = pytest.mark.unit


def make_user(username: str) -> User:
    user = User(username=username, email=f"{username}@example.com")
    user.set_password("password")
    return user


def make_poll_post(author: User, body: str = "Which is best?", options: list[str] | None = None) -> Post:
    if options is None:
        options = ["Option A", "Option B"]
    post = Post(author=author, body=body, is_poll=True)
    poll = Poll(post=post)
    for i, text in enumerate(options):
        poll.options.append(PollOption(text=text, position=i))
    return post


def test_poll_post_created_with_options(app):
    with app.app_context():
        alice = make_user("alice")
        db.session.add(alice)
        db.session.flush()
        post = make_poll_post(alice, "Best language?", ["Python", "JavaScript", "Go"])
        db.session.add(post)
        db.session.commit()

        assert post.is_poll is True
        assert post.poll is not None
        assert len(post.poll.options) == 3
        assert [o.text for o in post.poll.options] == ["Python", "JavaScript", "Go"]


def test_poll_total_votes_zero_initially(app):
    with app.app_context():
        alice = make_user("alice")
        db.session.add(alice)
        db.session.flush()
        post = make_poll_post(alice)
        db.session.add(post)
        db.session.commit()
        assert post.poll.total_votes() == 0


def test_poll_vote_and_percentage(app):
    with app.app_context():
        alice = make_user("alice")
        bob = make_user("bob")
        db.session.add_all([alice, bob])
        db.session.flush()
        post = make_poll_post(alice, options=["Yes", "No"])
        db.session.add(post)
        db.session.commit()

        poll = post.poll
        opt_yes = poll.options[0]
        opt_no = poll.options[1]
        db.session.add(PollVote(poll=poll, option=opt_yes, voter=alice))
        db.session.add(PollVote(poll=poll, option=opt_no, voter=bob))
        db.session.commit()

        assert poll.total_votes() == 2
        assert opt_yes.vote_count() == 1
        assert opt_yes.percentage(2) == 50.0
        assert opt_no.percentage(2) == 50.0


def test_poll_user_voted_option_id(app):
    with app.app_context():
        alice = make_user("alice")
        db.session.add(alice)
        db.session.flush()
        post = make_poll_post(alice)
        db.session.add(post)
        db.session.commit()

        poll = post.poll
        opt = poll.options[0]
        assert poll.user_voted_option_id(alice.id) is None
        db.session.add(PollVote(poll=poll, option=opt, voter=alice))
        db.session.commit()
        assert poll.user_voted_option_id(alice.id) == opt.id


def test_duplicate_vote_raises_integrity_error(app):
    with app.app_context():
        alice = make_user("alice")
        db.session.add(alice)
        db.session.flush()
        post = make_poll_post(alice)
        db.session.add(post)
        db.session.commit()

        poll = post.poll
        opt = poll.options[0]
        db.session.add(PollVote(poll=poll, option=opt, voter=alice))
        db.session.commit()

        db.session.add(PollVote(poll=poll, option=opt, voter=alice))
        with pytest.raises(IntegrityError):
            db.session.commit()


def test_poll_percentage_with_zero_total(app):
    with app.app_context():
        alice = make_user("alice")
        db.session.add(alice)
        db.session.flush()
        post = make_poll_post(alice)
        db.session.add(post)
        db.session.commit()
        option = post.poll.options[0]
        assert option.percentage(0) == 0.0

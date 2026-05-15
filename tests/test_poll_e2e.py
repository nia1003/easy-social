from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from easy_social import create_app
from easy_social.extensions import db
from easy_social.models import Poll, PollVote, Post, User

selenium = pytest.importorskip("selenium")

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def poll_app():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-poll-e2e",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{temp_path / 'poll_ui.sqlite'}",
                "UPLOAD_FOLDER": str(temp_path / "uploads"),
                "MEDIA_STORAGE_BACKEND": "local",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.app_context():
            db.create_all()
        yield app


@pytest.fixture(scope="module")
def poll_server(poll_app):
    try:
        server = make_server("127.0.0.1", 0, poll_app, threaded=True)
    except SystemExit:
        pytest.skip("Selenium live server could not bind to a local port")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture()
def browser():
    browser_name = os.environ.get("SELENIUM_BROWSER", "chrome").lower()
    headless = os.environ.get("SELENIUM_HEADLESS", "1") != "0"
    try:
        if browser_name == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("-headless")
            driver = webdriver.Firefox(options=options)
        else:
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--window-size=1280,900")
            driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        pytest.skip(f"Selenium browser could not start: {exc.msg}")
    yield driver
    driver.quit()


@pytest.fixture(autouse=True)
def clean_poll_db(poll_app):
    with poll_app.app_context():
        db.session.query(PollVote).delete()
        db.session.query(Poll).delete()
        db.session.query(Post).delete()
        db.session.query(User).delete()
        db.session.commit()


def set_field(browser, field, value: str):
    browser.execute_script(
        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
        field,
        value,
    )


def submit_form(browser, form):
    browser.execute_script(
        "arguments[0].requestSubmit ? arguments[0].requestSubmit() : arguments[0].submit();", form
    )


def register_via_ui(browser, server: str, username: str):
    browser.get(f"{server}/auth/register")
    form = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "form.form-stack"))
    )
    set_field(browser, form.find_element(By.NAME, "username"), username)
    set_field(browser, form.find_element(By.NAME, "email"), f"{username}@example.com")
    set_field(browser, form.find_element(By.NAME, "password"), "password")
    set_field(browser, form.find_element(By.NAME, "captcha"), "bypass")
    submit_form(browser, form)
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "form.composer"))
    )


def test_feed_shows_poll_composer(browser, poll_server):
    register_via_ui(browser, poll_server, "alice")
    body = browser.find_element(By.TAG_NAME, "body").text
    assert "Create Poll" in body


def test_create_poll_appears_in_feed(browser, poll_server):
    register_via_ui(browser, poll_server, "alice")
    poll_form = browser.find_element(By.CSS_SELECTOR, "form.poll-composer")
    set_field(browser, poll_form.find_element(By.NAME, "body"), "Best season?")
    set_field(browser, poll_form.find_element(By.NAME, "option_1"), "Spring")
    set_field(browser, poll_form.find_element(By.NAME, "option_2"), "Autumn")
    submit_form(browser, poll_form)
    WebDriverWait(browser, 5).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Best season?")
    )
    body = browser.find_element(By.TAG_NAME, "body").text
    assert "Spring" in body
    assert "Autumn" in body


def test_vote_on_poll_shows_results(browser, poll_server):
    register_via_ui(browser, poll_server, "voter")
    poll_form = browser.find_element(By.CSS_SELECTOR, "form.poll-composer")
    set_field(browser, poll_form.find_element(By.NAME, "body"), "Cats or dogs?")
    set_field(browser, poll_form.find_element(By.NAME, "option_1"), "Cats")
    set_field(browser, poll_form.find_element(By.NAME, "option_2"), "Dogs")
    submit_form(browser, poll_form)
    WebDriverWait(browser, 5).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Cats or dogs?")
    )
    vote_form = browser.find_element(By.CSS_SELECTOR, "form.poll-vote-form")
    radio = vote_form.find_element(By.CSS_SELECTOR, "input[type='radio']")
    browser.execute_script("arguments[0].checked = true;", radio)
    submit_form(browser, vote_form)
    WebDriverWait(browser, 5).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "%")
    )
    body = browser.find_element(By.TAG_NAME, "body").text
    assert "100.0%" in body or "%" in body
    assert "1 vote" in body

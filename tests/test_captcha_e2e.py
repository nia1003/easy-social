from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from easy_social import create_app
from easy_social.extensions import db
from easy_social.models import User

selenium = pytest.importorskip("selenium")

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def captcha_app():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-captcha-e2e",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{temp_path / 'captcha_ui.sqlite'}",
                "UPLOAD_FOLDER": str(temp_path / "uploads"),
                "MEDIA_STORAGE_BACKEND": "local",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.app_context():
            db.create_all()
        yield app


@pytest.fixture(scope="module")
def captcha_server(captcha_app):
    try:
        server = make_server("127.0.0.1", 0, captcha_app, threaded=True)
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
def clean_captcha_db(captcha_app):
    with captcha_app.app_context():
        db.session.query(User).delete()
        db.session.commit()


def wait_for(browser, selector, timeout=10):
    return WebDriverWait(browser, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def set_field(browser, field, value: str):
    browser.execute_script(
        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
        field,
        value,
    )


def test_register_page_shows_captcha_field(browser, captcha_server):
    browser.get(f"{captcha_server}/auth/register")
    form = wait_for(browser, "form.form-stack")
    body = browser.find_element(By.TAG_NAME, "body").text
    assert "CAPTCHA" in body
    assert "What is" in body
    captcha_input = form.find_element(By.NAME, "captcha")
    assert captcha_input is not None


def test_register_with_wrong_captcha_shows_error(browser, captcha_server):
    browser.get(f"{captcha_server}/auth/register")
    form = wait_for(browser, "form.form-stack")
    set_field(browser, form.find_element(By.NAME, "username"), "testuser")
    set_field(browser, form.find_element(By.NAME, "email"), "testuser@example.com")
    set_field(browser, form.find_element(By.NAME, "password"), "password")
    set_field(browser, form.find_element(By.NAME, "captcha"), "999")
    browser.execute_script(
        "arguments[0].requestSubmit ? arguments[0].requestSubmit() : arguments[0].submit();",
        form,
    )
    WebDriverWait(browser, 5).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Incorrect CAPTCHA")
    )
    body = browser.find_element(By.TAG_NAME, "body").text
    assert "Incorrect CAPTCHA" in body


def test_register_with_correct_captcha_succeeds(browser, captcha_server, captcha_app):
    browser.get(f"{captcha_server}/auth/register")
    form = wait_for(browser, "form.form-stack")
    body_text = browser.find_element(By.TAG_NAME, "body").text
    import re
    match = re.search(r"What is (\d+) \+ (\d+)", body_text)
    assert match, "CAPTCHA question not found in page"
    expected_answer = str(int(match.group(1)) + int(match.group(2)))

    set_field(browser, form.find_element(By.NAME, "username"), "captcha_user")
    set_field(browser, form.find_element(By.NAME, "email"), "captcha_user@example.com")
    set_field(browser, form.find_element(By.NAME, "password"), "password")
    set_field(browser, form.find_element(By.NAME, "captcha"), expected_answer)
    browser.execute_script(
        "arguments[0].requestSubmit ? arguments[0].requestSubmit() : arguments[0].submit();",
        form,
    )
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "form.composer"))
    )
    WebDriverWait(browser, 5).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Feed")
    )
    with captcha_app.app_context():
        assert User.query.filter_by(username="captcha_user").first() is not None

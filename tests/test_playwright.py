"""Playwright end-to-end tests for test mode feature (Flask web app + PWA)."""

from __future__ import annotations

import socket
import threading
import time

import pytest
from playwright.sync_api import Page, expect

from wiki_acronyms.api import api_bp
from wiki_acronyms.web_app import create_app
from wiki_acronyms.logger import QuizLogger
from wiki_acronyms.srs import SRSScheduler

_LINES = [
    "From fairest creatures we desire increase,",
    "That thereby beauty's rose might never die,",
    "But as the riper should by time decrease,",
]


def _make_app():
    """Create a test Flask app with fresh in-memory DB and PWA static serving."""
    logger = QuizLogger(db_path=":memory:")
    srs = SRSScheduler(logger)
    app = create_app(
        _LINES, "Sonnet 1", wrong_prob=0.0, mode="words",
        logger=logger, srs=srs,
    )
    app.register_blueprint(api_bp)   # enables /pwa/* static file serving
    app.config["TESTING"] = True
    return app


def _free_port() -> int:
    """Return an OS-assigned free TCP port."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_server():
    """Start a fresh Flask server on a free port for each test."""
    port = _free_port()
    app = _make_app()

    def _run():
        app.run(port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.3)
    yield f"http://localhost:{port}"


# ── Flask web-app tests ───────────────────────────────────────────────────────

def test_radio_buttons_present(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    expect(page.locator('input[name="test_mode"][value="0"]')).to_be_visible()
    expect(page.locator('input[name="test_mode"][value="1"]')).to_be_visible()


def test_default_is_study_mode(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    expect(page.locator('input[name="test_mode"][value="0"]')).to_be_checked()
    expect(page.locator('input[name="test_mode"][value="1"]')).not_to_be_checked()


def test_no_test_badge_in_study_mode(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    expect(page.locator(".test-badge")).not_to_be_visible()


def test_study_and_test_labels_visible(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    # Use exact=True to avoid matching "Sonnet 1" or other text containing "Test"
    expect(page.get_by_text("Study", exact=True)).to_be_visible()
    expect(page.get_by_text("Test", exact=True)).to_be_visible()


def test_submit_in_study_mode_no_badge(page: Page, live_server):
    """After submitting in study mode, no test badge on the next card."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="0"]').check()
    page.fill('input[name="answer"]', "")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page.locator(".test-badge")).not_to_be_visible()


def test_test_mode_badge_appears_after_submit(page: Page, live_server):
    """After submitting with test mode selected, badge shows on next card."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page.locator(".test-badge")).to_be_visible()
    expect(page.get_by_text("Test mode")).to_be_visible()


def test_test_mode_radio_pre_selected_after_switch(page: Page, live_server):
    """Radio button stays on Test after a submission in test mode."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page.locator('input[name="test_mode"][value="1"]')).to_be_checked()
    expect(page.locator('input[name="test_mode"][value="0"]')).not_to_be_checked()


def test_card_advances_in_test_mode(page: Page, live_server):
    """Correct answer in test mode advances to the next card."""
    page.goto(f"{live_server}/quiz")
    first_token = page.locator(".token-text").first.text_content()
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")  # wrong_prob=0 → no wrongs → correct
    with page.expect_navigation():
        page.click('button[type="submit"]')
    second_token = page.locator(".token-text").first.text_content()
    assert first_token != second_token, "Card did not advance in test mode"


def test_switch_back_to_study_removes_badge(page: Page, live_server):
    """Switching back to study mode removes the badge."""
    page.goto(f"{live_server}/quiz")
    # First go to test mode
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page.locator(".test-badge")).to_be_visible()

    # Switch back to study mode
    page.locator('input[name="test_mode"][value="0"]').check()
    page.fill('input[name="answer"]', "")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page.locator(".test-badge")).not_to_be_visible()


def test_feedback_shown_in_test_mode(page: Page, live_server):
    """Test mode still shows correct/wrong feedback flash after submit."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    # Flash feedback must be in DOM after the POST→redirect→GET cycle
    expect(page.locator(".feedback")).to_be_attached()


# ── PWA tests ─────────────────────────────────────────────────────────────────

def test_pwa_radio_buttons_present(page: Page, live_server):
    """PWA quiz.html has Study and Test radio buttons in the header."""
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=x&deck_name=Test&mode=words")
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator('#studyRadio')).to_be_attached()
    expect(page.locator('#testRadio')).to_be_attached()


def test_pwa_default_is_study(page: Page, live_server):
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=x&deck_name=Test&mode=words")
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator('#studyRadio')).to_be_checked()
    expect(page.locator('#testRadio')).not_to_be_checked()


def test_pwa_study_and_test_labels_visible(page: Page, live_server):
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=x&deck_name=Test&mode=words")
    page.wait_for_load_state("domcontentloaded")
    # Labels are inside the mode-toggle div
    toggle = page.locator('#modeToggle')
    expect(toggle.get_by_text("Study", exact=True)).to_be_visible()
    expect(toggle.get_by_text("Test", exact=True)).to_be_visible()


def test_pwa_toggle_to_test_mode(page: Page, live_server):
    """Clicking the Test label in PWA checks the Test radio."""
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=x&deck_name=Test&mode=words")
    page.wait_for_load_state("domcontentloaded")
    # Radio inputs are display:none; click the visible label instead
    page.locator('#modeToggle label:has(#testRadio)').click()
    expect(page.locator('#testRadio')).to_be_checked()
    expect(page.locator('#studyRadio')).not_to_be_checked()


def test_pwa_toggle_back_to_study(page: Page, live_server):
    """Can toggle back from Test to Study in PWA."""
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=x&deck_name=Test&mode=words")
    page.wait_for_load_state("domcontentloaded")
    page.locator('#modeToggle label:has(#testRadio)').click()
    page.locator('#modeToggle label:has(#studyRadio)').click()
    expect(page.locator('#studyRadio')).to_be_checked()
    expect(page.locator('#testRadio')).not_to_be_checked()

"""Playwright end-to-end tests for test mode feature (Flask web app + PWA)."""

from __future__ import annotations

import threading
import time

import pytest
from playwright.sync_api import Page, expect

from wiki_acronyms.web_app import create_app
from wiki_acronyms.logger import QuizLogger
from wiki_acronyms.srs import SRSScheduler

_LINES = [
    "From fairest creatures we desire increase,",
    "That thereby beauty's rose might never die,",
    "But as the riper should by time decrease,",
]

_PORT = 15099


def _make_app():
    """Create a test Flask app with a real (in-memory) logger and SRS."""
    logger = QuizLogger(db_path=":memory:")
    srs = SRSScheduler(logger)
    return create_app(
        _LINES, "Test Sonnet", wrong_prob=0.0, mode="words",
        logger=logger, srs=srs,
    )


@pytest.fixture(scope="module")
def live_server():
    """Start a Flask server for Playwright tests."""
    app = _make_app()
    app.config["TESTING"] = True

    def _run():
        app.run(port=_PORT, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.5)  # wait for Flask to bind
    yield f"http://localhost:{_PORT}"


# ── Flask web-app tests ───────────────────────────────────────────────────────

def test_radio_buttons_present(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    expect(page.locator('input[name="test_mode"][value="0"]')).to_be_visible()
    expect(page.locator('input[name="test_mode"][value="1"]')).to_be_visible()


def test_default_is_study_mode(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    study_radio = page.locator('input[name="test_mode"][value="0"]')
    test_radio = page.locator('input[name="test_mode"][value="1"]')
    expect(study_radio).to_be_checked()
    expect(test_radio).not_to_be_checked()


def test_no_test_badge_in_study_mode(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    expect(page.locator(".test-badge")).not_to_be_visible()


def test_study_labels_visible(page: Page, live_server):
    page.goto(f"{live_server}/quiz")
    expect(page.get_by_text("Study")).to_be_visible()
    expect(page.get_by_text("Test")).to_be_visible()


def test_submit_in_study_mode_no_badge(page: Page, live_server):
    """After submitting in study mode, no test badge appears on the next card."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="0"]').check()
    page.fill('input[name="answer"]', "")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    expect(page.locator(".test-badge")).not_to_be_visible()


def test_test_mode_badge_appears_after_submit(page: Page, live_server):
    """After submitting with test mode selected, badge shows on next card."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    # Badge visible on the next card
    expect(page.locator(".test-badge")).to_be_visible()
    expect(page.get_by_text("Test mode")).to_be_visible()


def test_test_mode_radio_pre_selected_after_switch(page: Page, live_server):
    """Radio button stays on Test after a submission in test mode."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    expect(page.locator('input[name="test_mode"][value="1"]')).to_be_checked()
    expect(page.locator('input[name="test_mode"][value="0"]')).not_to_be_checked()


def test_card_advances_in_test_mode(page: Page, live_server):
    """Correct answer in test mode advances to the next card."""
    page.goto(f"{live_server}/quiz")
    first_token = page.locator(".token-text").first.text_content()
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")  # wrong_prob=0 → no wrongs → correct
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    second_token = page.locator(".token-text").first.text_content()
    assert first_token != second_token, "Card did not advance in test mode"


def test_switch_back_to_study_removes_badge(page: Page, live_server):
    """Switching back to study mode removes the badge."""
    page.goto(f"{live_server}/quiz")
    # First go to test mode
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    expect(page.locator(".test-badge")).to_be_visible()

    # Now switch back to study
    page.locator('input[name="test_mode"][value="0"]').check()
    page.fill('input[name="answer"]', "")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    expect(page.locator(".test-badge")).not_to_be_visible()


def test_feedback_shown_in_test_mode(page: Page, live_server):
    """Test mode still shows correct/wrong feedback."""
    page.goto(f"{live_server}/quiz")
    page.locator('input[name="test_mode"][value="1"]').check()
    page.fill('input[name="answer"]', "")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/quiz")
    # Flash message should be present
    feedback = page.locator(".feedback")
    expect(feedback).to_be_visible()


# ── PWA tests ─────────────────────────────────────────────────────────────────

def test_pwa_radio_buttons_present(page: Page, live_server):
    """PWA quiz.html has Study and Test radio buttons in the header."""
    # Navigate directly to the PWA quiz page (no deck loaded — just check DOM)
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=test&deck_name=Test&mode=words")
    expect(page.locator('#studyRadio')).to_be_attached()
    expect(page.locator('#testRadio')).to_be_attached()


def test_pwa_default_is_study(page: Page, live_server):
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=test&deck_name=Test&mode=words")
    expect(page.locator('#studyRadio')).to_be_checked()
    expect(page.locator('#testRadio')).not_to_be_checked()


def test_pwa_study_label_visible(page: Page, live_server):
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=test&deck_name=Test&mode=words")
    expect(page.get_by_text("Study")).to_be_visible()
    expect(page.get_by_text("Test")).to_be_visible()


def test_pwa_toggle_to_test_mode(page: Page, live_server):
    """Clicking the Test radio in PWA marks it checked."""
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=test&deck_name=Test&mode=words")
    page.locator('#testRadio').check()
    expect(page.locator('#testRadio')).to_be_checked()
    expect(page.locator('#studyRadio')).not_to_be_checked()


def test_pwa_toggle_back_to_study(page: Page, live_server):
    """Can toggle back from Test to Study in PWA."""
    page.goto(f"{live_server}/pwa/quiz.html?deck_id=test&deck_name=Test&mode=words")
    page.locator('#testRadio').check()
    page.locator('#studyRadio').check()
    expect(page.locator('#studyRadio')).to_be_checked()
    expect(page.locator('#testRadio')).not_to_be_checked()

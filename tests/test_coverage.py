from unittest.mock import MagicMock, patch

from wiki_acronyms.coverage import (
    CoverageReport, _is_likely_person_link, check_coverage, fetch_wikipedia_list_links,
)
from wiki_acronyms.monarchs import Monarch


# _is_likely_person_link

def test_person_link_accepts_names():
    assert _is_likely_person_link("William I of England")
    assert _is_likely_person_link("Henry VIII")
    assert _is_likely_person_link("Elizabeth II")
    assert _is_likely_person_link("Æthelred the Unready")


def test_person_link_rejects_list_articles():
    assert not _is_likely_person_link("List of English monarchs")
    assert not _is_likely_person_link("Lists of monarchs")


def test_person_link_rejects_house():
    assert not _is_likely_person_link("House of Windsor")
    assert not _is_likely_person_link("House of Tudor")


def test_person_link_rejects_kingdom():
    assert not _is_likely_person_link("Kingdom of England")
    assert not _is_likely_person_link("Duchy of Normandy")


def test_person_link_rejects_year():
    assert not _is_likely_person_link("1066")
    assert not _is_likely_person_link("1066–1087")
    assert not _is_likely_person_link("871")


def test_person_link_rejects_disambiguation():
    assert not _is_likely_person_link("Henry (disambiguation)")


def test_person_link_rejects_dynasty_suffix():
    assert not _is_likely_person_link("Plantagenet (dynasty)")


def test_person_link_rejects_namespaced():
    assert not _is_likely_person_link("Category:English monarchs")
    assert not _is_likely_person_link("File:Crown.jpg")
    assert not _is_likely_person_link("Template:Infobox royalty")


# fetch_wikipedia_list_links

def test_fetch_wikipedia_list_links_filters():
    mock_client = MagicMock()
    mock_client.fetch_article_links.return_value = {
        "William I of England",
        "House of Normandy",
        "List of English monarchs",
        "1066",
        "Henry VIII",
    }
    result = fetch_wikipedia_list_links("List of English monarchs", api_client=mock_client)
    assert "William I of England" in result
    assert "Henry VIII" in result
    assert "House of Normandy" not in result
    assert "List of English monarchs" not in result
    assert "1066" not in result


def test_fetch_wikipedia_list_links_calls_correct_title():
    mock_client = MagicMock()
    mock_client.fetch_article_links.return_value = set()
    fetch_wikipedia_list_links("List of British monarchs", api_client=mock_client)
    mock_client.fetch_article_links.assert_called_once_with("List of British monarchs")


# check_coverage helpers

def _monarch(name, wp_title=None, accession_year=1000):
    return Monarch(name=name, accession_year=accession_year, end_year=None, father="", mother="", wp_title=wp_title)


# check_coverage

def test_check_coverage_all_matched():
    monarchs = [_monarch("William I", "William I of England")]
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=monarchs), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value={"William I of England"}):
        report = check_coverage(["Q18810062"], "List of English monarchs", subject="Test")
    assert report.wikidata_count == 1
    assert report.matched_count == 1
    assert report.in_wikipedia_not_wikidata == []
    assert report.in_wikidata_not_wikipedia == []
    assert report.no_wp_sitelink == []


def test_check_coverage_missing_from_wikidata():
    monarchs = [_monarch("William I", "William I of England")]
    wp_links = {"William I of England", "Harold II"}
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=monarchs), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value=wp_links):
        report = check_coverage(["Q18810062"], "List of English monarchs")
    assert "Harold II" in report.in_wikipedia_not_wikidata
    assert report.matched_count == 1


def test_check_coverage_missing_from_wikipedia():
    monarchs = [
        _monarch("William I", "William I of England"),
        _monarch("Harold II", "Harold II"),
    ]
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=monarchs), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value={"William I of England"}):
        report = check_coverage(["Q18810062"], "List of English monarchs")
    assert "Harold II" in report.in_wikidata_not_wikipedia
    assert report.matched_count == 1


def test_check_coverage_no_sitelink_reported_separately():
    monarchs = [_monarch("Æthelred the Unready", wp_title=None)]
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=monarchs), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value={"Æthelred the Unready"}):
        report = check_coverage(["Q18810062"], "List of English monarchs")
    assert "Æthelred the Unready" in report.no_wp_sitelink
    assert report.matched_count == 0


def test_check_coverage_empty_wikidata():
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=[]), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value={"William I of England"}):
        report = check_coverage(["Q18810062"], "List of English monarchs")
    assert report.wikidata_count == 0
    assert report.matched_count == 0
    assert "William I of England" in report.in_wikipedia_not_wikidata


def test_check_coverage_subject_propagated():
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=[]), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value=set()):
        report = check_coverage(["Q1"], "Some List", subject="English Monarchs")
    assert report.subject == "English Monarchs"
    assert report.wikipedia_list == "Some List"


def test_check_coverage_results_sorted():
    monarchs = [_monarch("Zara", "Zara"), _monarch("Anna", "Anna")]
    with patch("wiki_acronyms.coverage.fetch_monarchs", return_value=monarchs), \
         patch("wiki_acronyms.coverage.fetch_wikipedia_list_links", return_value=set()):
        report = check_coverage(["Q1"], "Some List")
    assert report.in_wikidata_not_wikipedia == sorted(report.in_wikidata_not_wikipedia)

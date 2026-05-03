"""Юнит-тесты для core/text_utils.py"""
import pytest
from core.text_utils import (
    normalize_spaces, clean_html_entities, clean_html_tags, clean_text,
    count_html_artifacts, extract_models, extract_articles,
    validate_photo_url, has_html_garbage, has_marketing_cliche,
)


class TestCleaning:
    def test_normalize_spaces(self):
        assert normalize_spaces("  a   b  c ") == "a b c"
        assert normalize_spaces("") == ""
        assert normalize_spaces(None) == ""

    def test_clean_html_entities(self):
        assert "&nbsp;" not in clean_html_entities("a&nbsp;b")
        assert "&mdash;" not in clean_html_entities("a&mdash;b")
        assert "&#160;" not in clean_html_entities("a&#160;b")

    def test_clean_html_tags(self):
        assert "<p>" not in clean_html_tags("<p>text</p>")
        assert "<br/>" not in clean_html_tags("a<br/>b")

    def test_clean_text_full(self):
        result = clean_text("<p>Колесо&nbsp;1М63</p>")
        assert "<p>" not in result
        assert "&nbsp;" not in result
        assert "Колесо" in result and "1М63" in result

    def test_clean_text_idempotent(self):
        text = "<p>Колесо&nbsp;1М63</p>"
        assert clean_text(clean_text(text)) == clean_text(text)

    def test_count_html_artifacts(self):
        # <p>, </p>, &nbsp; — три артефакта
        assert count_html_artifacts("<p>a&nbsp;b</p>") == 3
        assert count_html_artifacts("чистый текст") == 0


class TestExtraction:
    def test_extract_models(self):
        models = extract_models("Станок 1М63Н и 16К40")
        assert "1М63Н" in models
        assert "16К40" in models

    def test_extract_articles(self):
        articles = extract_articles("Артикул 16К40.03.152 на складе")
        assert "16К40.03.152" in articles


class TestValidation:
    def test_validate_photo_url_ok(self):
        assert validate_photo_url("https://site.ru/img.jpg") is True
        assert validate_photo_url("http://site.ru/img.png?v=1") is True

    def test_validate_photo_url_bad(self):
        assert validate_photo_url("") is False
        assert validate_photo_url(None) is False
        assert validate_photo_url("https://site.ru/page.html") is False

    def test_has_html_garbage(self):
        assert has_html_garbage("<p>text</p>") is True
        assert has_html_garbage("a&nbsp;b") is True
        assert has_html_garbage("чистый текст") is False

    def test_has_marketing_cliche(self):
        assert has_marketing_cliche("это лучшая цена на рынке") is True
        assert has_marketing_cliche("высокое качество гарантировано") is True
        assert has_marketing_cliche("сухой технический текст") is False

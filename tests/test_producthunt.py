"""Tests for Product Hunt data source."""

from trend_radar.models import SourceType
from trend_radar.sources.producthunt import ProductHuntSource


class TestProductHuntSource:
    def test_init(self):
        src = ProductHuntSource()
        assert src.name == "producthunt"
        assert src.source_type == SourceType.PRODUCTHUNT

    def test_parse_html_empty(self):
        src = ProductHuntSource()
        items = src._parse_html("", 10)
        assert items == []

    def test_parse_html_no_products(self):
        src = ProductHuntSource()
        items = src._parse_html("<html><body><p>Nothing here</p></body></html>", 10)
        assert items == []

    def test_parse_html_with_products(self):
        src = ProductHuntSource()
        html = """
        <html><body>
            <div>
                <a href="/posts/cool-app">Cool App</a>
                <p>A really cool application</p>
            </div>
            <div>
                <a href="/posts/another-tool">Another Tool</a>
                <p>A useful tool</p>
            </div>
        </body></html>
        """
        items = src._parse_html(html, 10)
        assert len(items) == 2
        assert items[0].title == "Cool App"
        assert items[0].source == SourceType.PRODUCTHUNT
        assert "/posts/cool-app" in items[0].url

    def test_parse_html_respects_limit(self):
        src = ProductHuntSource()
        html = "<html><body>"
        for i in range(20):
            html += f'<a href="/posts/item-{i}">Item {i}</a>'
        html += "</body></html>"

        items = src._parse_html(html, 5)
        assert len(items) == 5

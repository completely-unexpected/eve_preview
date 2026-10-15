import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.test import TestCase, override_settings

from . import services


@override_settings(ODDS_API_KEY="test-key-never-return")
class FeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.league = {"key": "soccer_epl", "title": "EPL", "group": "Soccer", "active": True, "has_outrights": False}
        self.match = {"id": "event1", "commence_time": "2026-10-20T18:00:00Z", "home_team": "Home <script>", "away_team": "Away"}

    @patch("sportsfeed.services.fetch")
    def test_public_response_uses_normalized_events_and_cache_without_key(self, fetch):
        fetch.side_effect = [[self.league], [self.match]]
        response = self.client.get("/api/sports/events/?league=soccer_epl")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["home"], "Home <script>")
        self.assertNotIn("test-key-never-return", response.content.decode())
        self.assertIn("no-store", response["Cache-Control"])
        self.client.get("/api/sports/events/?league=soccer_epl")
        self.assertEqual(fetch.call_count, 2)

    @patch("sportsfeed.services.fetch")
    def test_leagues_hide_outrights_and_inactive_entries(self, fetch):
        fetch.return_value = [self.league, {**self.league, "key": "winner", "has_outrights": True}, {**self.league, "active": False}]
        data = self.client.get("/api/sports/leagues/").json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["defaultLeague"], "soccer_epl")

    @patch("sportsfeed.services.fetch")
    def test_invalid_path_is_rejected_before_fetch(self, fetch):
        self.assertEqual(self.client.get("/api/sports/events/?league=../../secret").status_code, 400)
        fetch.assert_not_called()
        fetch.return_value = [self.league]
        self.assertEqual(self.client.get("/api/sports/events/?league=unknown").status_code, 400)
        self.assertEqual(fetch.call_count, 1)

    @patch("sportsfeed.services.urlopen")
    def test_provider_failure_never_returns_secret_or_request_url(self, opened):
        opened.side_effect = HTTPError("https://example.test/?apiKey=test-key-never-return", 401, "bad key", {}, None)
        response = self.client.get("/api/sports/leagues/")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("test-key-never-return", response.content.decode())
        self.assertNotIn("apiKey", response.content.decode())
        opened.side_effect = URLError("network down")
        self.assertEqual(self.client.get("/api/sports/leagues/").status_code, 503)

    @override_settings(ODDS_API_KEY="")
    @patch("sportsfeed.services.urlopen")
    def test_missing_key_does_not_call_provider(self, opened):
        self.assertEqual(self.client.get("/api/sports/leagues/").status_code, 503)
        opened.assert_not_called()

    @patch("sportsfeed.services.fetch")
    def test_malformed_events_are_skipped_and_empty_is_valid(self, fetch):
        fetch.side_effect = [[self.league], [{"bad": True}, {**self.match, "commence_time": "bad"}]]
        self.assertEqual(self.client.get("/api/sports/events/").json()["items"], [])

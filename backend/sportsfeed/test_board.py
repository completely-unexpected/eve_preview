from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .collector import collect, normalize_books
from .extra import load_extra
from .models import FeedSnapshot


@override_settings(ODDS_API_KEY="mock-private-key")
class BoardTests(TestCase):
    def setUp(self):
        self.league = {"key": "soccer_epl", "title": "EPL", "group": "Soccer", "active": True, "has_outrights": False}
        self.event = {"id": "event1", "home_team": "Home", "away_team": "Away", "commence_time": "2099-01-01T12:00:00Z"}
        self.book = {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [{"name": "Home", "price": 2.0}, {"name": "Away", "price": 1.8}]}]}

    @patch("sportsfeed.collector.request_json")
    def test_collection_persists_all_data_and_reuses_completed_snapshot(self, fetch):
        fetch.side_effect = [([self.league], {"remaining": 500}), ([self.event], {"remaining": 500}), ([{**self.event, "bookmakers": [self.book]}], {"remaining": 497}), ([], {"remaining": 496})]
        snapshot = collect()
        self.assertTrue(snapshot.payload["complete"])
        self.assertFalse(snapshot.syncing)
        self.assertEqual(len(snapshot.payload["items"]), 1)
        self.assertEqual(snapshot.payload["remainingCredits"], 496)
        self.assertEqual(snapshot.payload["items"][0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"], "2.0000")
        collect()
        self.assertEqual(fetch.call_count, 4)
        response = self.client.get("/api/sports/board/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "mock-private-key")
        self.assertFalse(response.json()["canLoadExtra"])
        self.assertEqual(fetch.call_count, 4)

    @patch("sportsfeed.collector.request_json")
    def test_insufficient_credits_does_not_start_paid_requests(self, fetch):
        fetch.return_value = ([self.league], {"remaining": 3})
        snapshot = collect()
        self.assertFalse(snapshot.payload["complete"])
        self.assertEqual(fetch.call_count, 1)
        self.assertFalse(snapshot.syncing)

    def test_invalid_prices_are_excluded(self):
        self.book["markets"][0]["outcomes"] += [{"name": "invalid", "price": "NaN"}, {"name": "zero", "price": 0}, {"name": "huge", "price": "Infinity"}]
        markets = normalize_books([self.book])[0]["markets"]
        self.assertEqual(len(markets[0]["outcomes"]), 2)

    def saved_event(self):
        event = {"id": "event1", "home": "Home", "away": "Away", "leagueKey": "soccer_epl", "league": "EPL", "group": "Soccer", "startsAt": "2099-01-01T12:00:00+00:00", "bookmakers": normalize_books([self.book]), "status": "scheduled", "completed": False, "scores": None}
        return FeedSnapshot.objects.create(pk=1, payload={"items": [event], "remainingCredits": 10})

    @patch("sportsfeed.extra.request_json")
    def test_extra_markets_are_admin_only_cached_and_respect_credit_limit(self, fetch):
        self.saved_event()
        member = get_user_model().objects.create_user(username="regular_feed_member")
        admin = get_user_model().objects.create_superuser(username="feed_operator")
        with self.assertRaises(PermissionError): load_extra("event1", member)
        fetch.assert_not_called()
        extra = {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 2.5}]}
        fetch.side_effect = [({"bookmakers": [{"markets": [{"key": "h2h"}, {"key": "totals"}]}]}, {"remaining": 1}), ({"id": "event1", "bookmakers": [self.book]}, {"remaining": 0})]
        event, remaining = load_extra("event1", admin)
        self.assertFalse(event["extraMarkets"]["complete"])
        self.assertEqual(event["extraMarkets"]["requestedCount"], 1)
        self.assertEqual(remaining, 0)
        load_extra("event1", admin)
        self.assertEqual(fetch.call_count, 2)
        self.assertFalse(FeedSnapshot.objects.get().syncing)

    def test_extra_endpoint_enforces_authentication_csrf_and_method(self):
        self.assertEqual(self.client.post("/api/sports/extra-markets/", {"event_id": "event1"}).status_code, 401)
        member = get_user_model().objects.create_user(username="feed_member")
        self.client.force_login(member)
        self.assertEqual(self.client.post("/api/sports/extra-markets/", {"event_id": "event1"}).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(member)
        self.assertEqual(csrf_client.post("/api/sports/extra-markets/", {"event_id": "event1"}).status_code, 403)
        self.assertEqual(self.client.get("/api/sports/extra-markets/").status_code, 405)


    @patch("sportsfeed.collector.request_json")
    def test_full_refresh_preserves_existing_data_when_credits_are_insufficient(self, fetch):
        from .services import ProviderError
        snapshot = self.saved_event()
        snapshot.payload["complete"] = True
        snapshot.save()
        fetch.return_value = ([self.league], {"remaining": 3})
        with self.assertRaises(ProviderError): collect(force=True)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.payload["items"][0]["id"], "event1")
        self.assertTrue(snapshot.payload["complete"])
        self.assertFalse(snapshot.syncing)
        self.assertEqual(fetch.call_count, 1)

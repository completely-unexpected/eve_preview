"""Export the pinned upstream's supported league/market catalogue for our forms."""
import json
from pathlib import Path
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.core.sport_market_registry import SportMarketRegistry,SportMarketRegistrar
SportMarketRegistrar.register_all_markets()
data={'version':'0.20.0','leagues':{sport.value:leagues for sport,leagues in SPORTS_LEAGUES_URLS_MAPPING.items()},'markets':{sport:list(markets) for sport,markets in SportMarketRegistry._registry.items()}}
Path(__file__).with_name('supported.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

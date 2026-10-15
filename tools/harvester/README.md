# Separate OddsHarvester integration

Upstream: https://github.com/jordantete/OddsHarvester (MIT).
Pinned distribution: oddsharvester 0.20.0 from PyPI. We invoke the upstream CLI,
without modifying or vendoring its installed source. Its license is included
in the distribution. Review dependency upgrades before changing the pin.

Windows setup from the project root:

```powershell
.\.venv\Scripts\python.exe -m venv tools\harvester\.venv
.\tools\harvester\.venv\Scripts\python.exe -m pip install -r tools\harvester\requirements.txt
.\tools\harvester\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe backend\manage.py migrate
```

Open `/admin/sportsfeed/harvestersnapshot/`. This runs a detached Django worker
that calls the isolated CLI. It discovers links, then visits only the requested
maximum number of match pages, sequentially with a 2-second request delay.
Only one Harvester job can run at once. Stop affects Harvester only. Each CLI
stage has a 30-minute timeout; job heartbeats make abandoned jobs expire.
On deployment the web account must have access to the venv and Playwright browsers.

Upcoming: select a date, or optionally a league (league overrides date).
Historic: supply sport/country/league; only the first current-season results
page is selected. Live: one-shot snapshot, not a continuous streaming feed.
The selectors also support All: all supported sports, all three collection
modes, all known upstream leagues for historic collection, all registered
markets, and unlimited detail count. Detail limits apply per sport/mode.
All leagues on an upcoming date use the date listing; historic All uses the
pinned upstream catalogue in supported.json. Large All runs may take a long
time and each CLI stage still has a 30-minute timeout. Missing/ambiguous markets
remain missing rather than being fabricated. Exported catalogue data is from
OddsHarvester 0.20.0; its MIT notice is in UPSTREAM-LICENSE.txt.

Upcoming criteria use a Korean-local date and time (`datetime-local` input).
The date's kickoff list is filtered at the requested time, including when a
league is supplied. Unknown kickoff times are resolved on the detail page or
excluded when they cannot be verified. This filters matches, not the time when
the collector is scheduled to run.

In-play collection now lives at
`/admin/sportsfeed/harvestersnapshot/inplay/` under Registration Engine → Inplay.
Its results use InplaySnapshot. The normal form excludes live mode; its All
mode includes upcoming and historic only. OddsParsing's manual collection also
excludes live rows. Harvester and Inplay share a single concurrent-job lock,
and stop buttons affect only jobs belonging to their own screen.

Both forms offer All bookmakers, named presets, and a custom bookmaker name.
An empty job.target_bookmaker means All and adds no CLI filter. A selected name
is passed as a separate `--target-bookmaker` argument only on detail collection;
raw market rows and normalized markets are also filtered defensively by exact
case-insensitive name. Missing selected-book prices remain empty with a warning,
without substituting another bookmaker. Existing snapshots are not re-filtered
until a new collection completes.
The run log states the discovered and selected counts; a capped run is not an
assertion that every game has been collected.

HarvesterSnapshot is independent of FeedSnapshot and OddsPortalSnapshot.
The combined game administration supports source=harvester and manual price
overlays. Raw upstream records are retained for comparing market periods,
handicap lines and bookmaker names. Blocked outcomes are excluded from the
editable normalized odds. No automatic publishing, bet settlement, wallet
changes, or existing-feed replacement occurs in this integration.

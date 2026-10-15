# REA observation — 2026-10-15

Evidence: `ev_13dbcc005e462ee08f7ac8aaf921acebfb10db59cd9af62438cbed21b4f61208`

REA `capture_browser_scenario` launched installed Chrome 155 in headed mode, with empty storage, en-US locale, UTC timezone and service workers blocked. Public homepage requests `/api/auth-token` and `/proxy/api/home-data` returned HTTP 200. The captured DOM contained 74 match-link occurrences; these are not a deduplicated event count. Network bodies, authorization headers and storage values were not requested. Unfinished unrelated network requests limited full event-capture completeness.

The local collector was changed to match the observed browser configuration. A subsequent actual collection stored 73 unique events: 59 finished, 13 scheduled, one postponed. Scores and displayed odds were verified in the saved data. Prices load after event rows, so collection waits for numeric odds rather than immediately saving placeholders.

This verifies the observed public homepage collection only. It does not establish all-sport coverage, a specific bookmaker attribution, guaranteed future availability or automated settlement correctness. Existing slips remain separate.

The original observation used a 300-second watch and separate browser launches. Current
implementation uses a shared, authenticated local browser host and a 60-second pause
between passes; requests reuse one context/tab. No Windows startup task is installed.

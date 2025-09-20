Refactor: centralize market business logic and routing

Summary
- Centralized market business logic into `app.services.market_service.MarketService`.
- Made `app.market` (blueprint) the canonical routing surface for market-related endpoints.
- Removed duplicated handlers from `app.py` by delegating `/assegna_giocatore` and `/squadra/<team_name>` to `app.market`.
- Marked legacy helper wrappers in `app.py` as deprecated (they remain thin wrappers delegating to `MarketService` and will emit DeprecationWarning).

Testing
- Full unit + integration test suite: 14 passed locally (pytest).

Notes for reviewers
- Behavior preserved for web UI: HTML error pages and JSON error shapes are unchanged.
- After merging we can safely remove deprecated wrappers and shrink `app.py` to a minimal runner.

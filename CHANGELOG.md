# Changelog

All notable changes to this project should be documented in this file.

## [Unreleased]

- Refactor: centralize market business logic into `app.services.market_service.MarketService`.
- Add `app.db.get_connection()` to centralize sqlite connection creation and configure `Row` factory.
- Make `app.market` blueprint the canonical routing surface; delegate heavy logic to the service.
- Add tests for MarketService helpers (in-memory sqlite), increased test coverage.
- Tidy: remove unused `sqlite3` imports from app modules.


## Past

- See repository commit history.

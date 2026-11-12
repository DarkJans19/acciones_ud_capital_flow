# Implementation Plan: identity-market-backend

## Overview

Python 3.12 + FastAPI backend for MOD-01 (`identity`) and MOD-02 (`market_data`), following `design.md` and the hexagonal rules of `AGENTS.md`.

This spec (`.kiro/specs/identity-market-backend`) is the single documentation base for MOD-01 and MOD-02. `specs/01-identity-security` and `specs/02-market-data` are superseded and are not a source of requirements, paths or tasks. CSRF tokens and Origin or Referer validation are out of scope by decision D4: cookie protection relies on the `SameSite` attribute of the `access_token` and `refresh_token` cookies, and CORS stays restricted to the configured origins (Requirement 17.4).

The plan has four parts:

1. **Shared foundation (tasks 1-2):** settings and startup validation, error model, database helpers, Alpaca HTTP plumbing, auth cookie helpers, app wiring with CORS, and test infrastructure. Both owners depend on it, so it comes first.
2. **Two parallel tracks:**
   - MOD-01 `identity` (tasks 3-11), owner Daniel Sanabria.
   - MOD-02 `market_data` (tasks 12-19), owner Davidson Sánchez.
   The only code dependency from `market_data` on `identity` is the auth dependency in `identity/adapters/inbound/http/deps.py` (`CurrentUser`, `get_current_user`, `require_permission`, `require_premium`, `authenticate_access_token`), delivered early in task 3.10. Until then, `market_data` API tests override those dependencies with FastAPI `dependency_overrides`.
3. **Contract and integration (tasks 20-21):** OpenAPI error declarations and cross-module tests.
4. **MOD-01 `readme_agregar.md` gaps (tasks 22-30), owner Daniel Sanabria:** revision `0005_identity_admin_gaps`, logout with optional credentials (C1), broker activation with the investor role (A3), the broker request flag (D1), the administrative user directory with KYC data (A1, A2), the KYC status cache and KYC_Refresh_Job (B3), KYC reconciliation (B4) and the identity Audit_Log (D3). The section sits right after task 11 because it extends the finished identity track; it shares no source file with the MOD-02 track.

All REST paths are under `/api/v1` and follow the Plan Maestro paths of the design endpoint table. The WebSocket is `WS /ws/v1/market-feed`, outside the `/api/v1` prefix.

Reconciliations with the existing repository (no redesign):

- Error types live in the existing `src/acciones_ud/shared/domain/errors.py` (pure, extended with `ErrorCode` and `AppError`, keeping `DomainError` and `NotFoundError`). The FastAPI-specific `ErrorBody` model and the exception handlers go to `shared/infrastructure/http_errors.py`. There is no new `shared/errors.py`.
- Wiring lives in the existing per-module `identity/composition.py` and `market_data/composition.py`. `main.py` calls one `register(app)` hook and the `startup`/`shutdown` hooks of each module. There is no top-level `composition.py`.
- Alpaca error classes and the pure `classify` function go to `shared/domain/alpaca_errors.py`, so application use cases can catch them without importing infrastructure. The httpx client factory goes to `shared/infrastructure/alpaca_http.py`. The `Clock` port goes to `shared/domain/clock.py`.
- The helpers that set and clear the `access_token` and `refresh_token` cookies together go to `shared/infrastructure/cookies.py`, as in the design. There is no identity-local `cookies.py`.
- `identity.domain.totp_window.match` receives a TOTP code generator through a port. The `pyotp` wrapper is an outbound adapter, so the domain never imports a provider library.

Identity HTTP adapters are split by path group: `routers/auth.py` (`/auth/register`, `/auth/register/broker`, `/auth/login`, `/auth/mfa/verify`), `routers/sessions.py` (`/auth/refresh`, `/auth/logout`, `/users/me/sessions...`), `routers/users.py` (`/users/me`, `/users/me/interests`, `/users/me/mfa/recovery-codes`), `routers/preferences.py` (`/users/preferences/*`, `/users/me/telegram`), `routers/admin.py` (`/admin/users/...`, `/admin/roles...`, `/admin/permissions`, `/admin/kyc/{user_id}/reconcile`, `/admin/audit-log`) and `routers/kyc.py` (`/kyc/*`).

Validation commands (from `AGENTS.md`): `uv run ruff check .`, `uv run mypy src`, `uv run pytest`. Applying the Migration_Set with `uv run alembic upgrade head` is a manual developer step, not a gate.

## Tasks

- [x] 1. Shared foundation (both owners, do first)
  - [x] 1.1 Fix the Alembic revision template and configure per-revision transactions
    - In `migrations/script.py.mako` line 12, remove the trailing `So` after `${repr(up_revision)}`
    - Replace `Union[...]` annotations with `str | None` and `str | Sequence[str] | None`, and drop the unused `Union` import, so generated revisions pass `uv run ruff check .`
    - In `migrations/env.py`, pass `transaction_per_migration=True` to both `context.configure` calls; keep URL selection, the async engine and offline mode unchanged; keep `target_metadata = None`
    - _Requirements: 17.7_

  - [x] 1.2 Add dependencies and test configuration
    - `uv add email-validator httpx websockets argon2-cffi PyJWT pyotp cryptography pycountry tzdata`; `uv add --dev hypothesis asgi-lifespan` (moves `httpx` from dev to runtime)
    - In `pyproject.toml`: pytest `asyncio_mode = "auto"`
    - Create `tests/conftest.py` with a Hypothesis profile (`max_examples=100`)
    - _Requirements: 17.7_

  - [x] 1.3 Extend `Settings` and add startup validation
    - In `src/acciones_ud/config/settings.py`, keep `Settings`, `get_settings` and the existing fields; add every variable of the design "Configuration" table as an optional field (`SecretStr` for secrets), including `COOKIE_DOMAIN`
    - Keep `ALPACA_DATA_FEED` and `PRICE_STALENESS_THRESHOLD_SECONDS` (default `900`) as plain strings parsed by the validator, so a bad value never reaches a Pydantic error that echoes it
    - Add `require_api_settings(settings)` that reports every missing or empty required variable by name only, and rejects by name: a non-`postgresql+asyncpg://` URL, `sslmode=` or missing `ssl=require` (skipped when `APP_ENV=test`), `*` in `CORS_ALLOWED_ORIGINS`, a `JWT_SECRET` under 32 bytes, out-of-range TTLs and intervals, a `COOKIE_SAMESITE` other than `lax`/`strict`, an `ALPACA_DATA_FEED` other than `iex`, `sip` or `delayed_sip`, and a `PRICE_STALENESS_THRESHOLD_SECONDS` that is not an integer from 1 to 86,400
    - Add `InitialAdminSettings` (`env_prefix="INITIAL_ADMIN_"`), not part of `Settings`
    - Add every variable of both configuration tables to `.env.example` with placeholder values
    - _Requirements: 3.3, 13.17, 17.3, 17.8_

  - [x]* 1.4 Write property test for missing and invalid configuration
    - **Property 32: Missing configuration is reported by name only**
    - **Validates: Requirements 13.17, 17.3, 17.8**
    - File: `tests/shared/property/test_config_properties.py`

  - [x] 1.5 Implement the error model and HTTP error handlers
    - Extend `src/acciones_ud/shared/domain/errors.py` with `ErrorCode` (every code of the design "Error codes" table, including `BROKER_NOT_PENDING` and `MFA_NOT_ENROLLED`) and `AppError(DomainError)` carrying `status`, `code`, `message`, `details`; keep `DomainError` and `NotFoundError`; no FastAPI import
    - Create `src/acciones_ud/shared/infrastructure/http_errors.py` with the `ErrorBody` Pydantic model, `register_exception_handlers(app)` for `AppError`, `RequestValidationError` (422 `VALIDATION_ERROR`, message names the first invalid field, `details.errors` lists all, Pydantic `input` dropped), `StarletteHTTPException` and `Exception` (500 `INTERNAL_ERROR`, fixed message "An unexpected error occurred.", details null)
    - Add an `error_responses(*statuses)` helper that routers use to declare their error responses with the `ErrorBody` schema in OpenAPI
    - _Requirements: 17.2, 17.10, 1.7, 10.2_

  - [x] 1.6 Write property test for unexpected errors
    - **Property 33: Unexpected errors produce a fixed, safe body**
    - **Validates: Requirements 17.10**
    - File: `tests/shared/property/test_error_properties.py`; also one example test for the 422 `VALIDATION_ERROR` shape without echoed input

  - [x] 1.7 Add the Clock port
    - `src/acciones_ud/shared/domain/clock.py`: `Clock` Protocol with `now() -> datetime` (aware UTC) and `SystemClock`
    - `tests/support/clock.py`: controllable `FakeClock` (set and advance)
    - _Requirements: 3.1, 3.3, 5.7, 12.5, 13.11_

  - [x] 1.8 Add logging with secret redaction and request ids
    - `src/acciones_ud/shared/infrastructure/logging.py`: JSON formatter, `SecretRedactionFilter` that replaces every configured secret value (Alpaca key and secret, JWT secret, Fernet key, password inside `DATABASE_URL`) with `***`, `httpx`/`httpcore` loggers at `WARNING`, and a middleware that sets `X-Request-ID`; request headers and bodies are never logged
    - _Requirements: 17.3, 3.7, 18.2_

  - [x] 1.9 Extend the database module
    - In `src/acciones_ud/shared/infrastructure/db.py`, keep `require_database_url`, `engine`, `session_factory`, `get_session`
    - Add `build_engine(url)` with `pool_pre_ping=True`, `pool_timeout=10`, `connect_args={"statement_cache_size": 0, "prepared_statement_name_func": <unique name>, "command_timeout": 10}`, and make the module-level `engine` use it
    - Add `unit_of_work()` (session + `session.begin()`) and a DB error translator that maps connection failures, pool timeouts and statement timeouts to `AppError(503, DATABASE_UNAVAILABLE)`
    - _Requirements: 1.9, 3.12, 9.6, 17.9_

  - [x] 1.10 Add shared Alpaca error classification and HTTP client factory
    - `src/acciones_ud/shared/domain/alpaca_errors.py`: `AlpacaError` and subclasses `AlpacaUnavailable`, `AlpacaRateLimited`, `AlpacaValidationError(message)`, `AlpacaNotFound`, `AlpacaAuthError`; pure `classify(status_code | exception)`; `to_app_error(exc)` mapping to 502 `ALPACA_UNAVAILABLE`, 503 `ALPACA_RATE_LIMITED`, 404 `SYMBOL_NOT_FOUND`, 500 `INTERNAL_ERROR`; the raw Alpaca body is never copied
    - `src/acciones_ud/shared/infrastructure/alpaca_http.py`: shared `httpx.AsyncClient` factory per host (Basic auth, 10 s timeout, no retries) and `raise_for_alpaca(response)`
    - _Requirements: 17.5, 17.6_

  - [x]* 1.11 Write property test for Alpaca error classification
    - **Property 30: Alpaca error classification**
    - **Validates: Requirements 17.5, 17.6**
    - File: `tests/shared/property/test_alpaca_errors_properties.py`

  - [x] 1.12 Wire the application shell in `main.py`
    - Keep `create_app()` and the unprefixed `/health` endpoint
    - Add a lifespan that calls `require_api_settings`, configures logging, builds the Alpaca HTTP clients, and calls `identity.composition.startup/shutdown` and `market_data.composition.startup/shutdown`
    - Add `CORSMiddleware` with the exact configured origins, `allow_credentials=True`, the methods `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS` and the request header `Content-Type`; add the request id middleware and `register_exception_handlers`
    - Add `register(app)`, `startup(app)` and `shutdown(app)` hooks to `identity/composition.py` and `market_data/composition.py` (each module includes its REST routers under `/api/v1`); import `shared.infrastructure.db` lazily inside providers so importing `acciones_ud.main` needs no database
    - `tests/unit/test_health.py` must keep passing without environment variables
    - _Requirements: 17.1, 17.4, 17.8_

  - [x] 1.13 Write property test for CORS
    - **Property 31: CORS never reflects an unlisted origin**
    - **Validates: Requirements 17.4**
    - File: `tests/shared/property/test_cors_properties.py`

  - [x] 1.14 Add settings and ASGI test fixtures
    - In `tests/conftest.py`: a settings fixture with `APP_ENV=test` and test `INITIAL_ADMIN_*` values that clears the `get_settings` cache
    - Async ASGI client fixture using `httpx.ASGITransport` and `asgi-lifespan`, with use cases and unit-of-work factories replaced by in-memory fakes through the `request.app.state` overrides and `dependency_overrides`; no fixture connects to a database
    - _Requirements: 17.7_

  - [x] 1.15 Implement the auth cookie helpers
    - `src/acciones_ud/shared/infrastructure/cookies.py`: fixed names `access_token` (HttpOnly, `Path=/`, `Max-Age=ACCESS_TOKEN_TTL_SECONDS`) and `refresh_token` (HttpOnly, `Path=/api/v1/auth`, `Max-Age=REFRESH_TOKEN_TTL_SECONDS`); both with `Secure`, `SameSite=<COOKIE_SAMESITE>` and `Domain=<COOKIE_DOMAIN>` when set
    - `set_auth_cookies(response, access, refresh)` sets both cookies together; `clear_auth_cookies(response)` clears both together
    - _Requirements: 3.3, 4.1, 4.2, 4.4, 4.6, 4.8_

  - [x]* 1.16 Write unit tests for the cookie helpers
    - File: `tests/shared/unit/test_cookies.py`: attributes of each cookie (HttpOnly, Secure, configured SameSite, path, Max-Age, optional Domain), set writes exactly `access_token` and `refresh_token`, clear removes both
    - _Requirements: 3.3, 4.2_

- [ ] 2. Checkpoint - Shared foundation
  - Ensure all tests pass, ask the user if questions arise.

### MOD-01 identity track (owner: Daniel Sanabria)

- [x] 3. Identity schema, security primitives and the auth dependency
  - [x] 3.1 Write migration `0001_identity_schema`
    - `migrations/versions/0001_identity_schema.py`, `revision = "0001_identity_schema"`, `down_revision = None`
    - Create `roles`, `permissions`, `role_permissions`, `users`, `role_assignments`, `mfa_challenges`, `mfa_recovery_codes`, `sessions`, `refresh_tokens`, `auth_events`, `notification_preferences`, `portfolio_view_settings`, `order_controls`, `kyc_accounts` with every column, check constraint and index of the design "Tables", including `users.account_status` (`active`/`pending_broker_activation`, default `active`), `users.firm_name`, `users.license_number`, the partial index on unused `mfa_recovery_codes`, `auth_events.method` (`totp`/`recovery_code`) and the `invalid_recovery_code` result
    - Enable RLS on each table and on `alembic_version`; seed the three roles, the permission codes and the role-permission pairs of "RBAC seed"
    - `downgrade()` drops the tables in reverse foreign-key order
    - _Requirements: 2.1, 2.11, 5.1, 7.1, 7.2, 17.7, 18.1_

  - [x] 3.2 Define identity domain entities and ports
    - `identity/domain/entities.py`: `User` (with `account_status`), `Session`, `RoleAssignment`, `MfaChallenge`, `RecoveryCode`, `CurrentUser` (`user_id`, `session_id`, `email`, names, `account_status`, `is_premium`, `effective_roles`, `permissions`) as dataclasses
    - `identity/domain/ports.py`: repository Protocols (including `RecoveryCodeRepository`), `PasswordHasher`, `AccessTokenCodec`, `RefreshTokenGenerator`, `TotpGenerator`, `SecretCipher`, `AlpacaAccountsPort`, `InterestCatalogPort`
    - No FastAPI, SQLAlchemy or provider imports
    - _Requirements: 2.11, 3.8, 5.8, 10.1, 18.1_

  - [x] 3.3 Implement RBAC rules
    - `identity/domain/rbac.py`: `is_effective(assignment, account_status, t)` (false unless `account_status == "active"`), `effective_roles`, `has_permission`, `would_remove_last_admin(assignments, change, t)`
    - _Requirements: 2.11, 5.5, 5.7, 5.8, 5.9, 5.10_

  - [x] 3.4 Write property test for effective roles and permission checks
    - **Property 7: Effective roles and permission checks**
    - **Validates: Requirements 2.11, 5.5, 5.7, 5.8, 5.9**
    - File: `tests/identity/property/test_rbac_properties.py`

  - [x] 3.5 Write property test for the last-administrator guard
    - **Property 9: The last administrator cannot be removed**
    - **Validates: Requirements 5.10**
    - File: `tests/identity/property/test_last_admin_properties.py`

  - [x] 3.6 Implement security adapters
    - `identity/adapters/outbound/security/`: Argon2id `PasswordHasher` (with a dummy hash for unknown emails; also used for recovery code hashes), HS256 `AccessTokenCodec` (`sub`, `sid`, `iat`, `exp`) using the injected `Clock`, refresh token generator (32 random bytes, URL-safe base64, SHA-256 hash), Fernet `SecretCipher`
    - _Requirements: 1.3, 3.3, 3.9, 4.1, 18.1_

  - [x]* 3.7 Write property test for password hashing
    - **Property 3: Password hashing round trip**
    - **Validates: Requirements 1.3**
    - File: `tests/identity/property/test_password_hash_properties.py` (`deadline=None`)

  - [x] 3.8 Write property test for the access token codec
    - **Property 6: Access token codec**
    - **Validates: Requirements 3.3, 3.9**
    - File: `tests/identity/property/test_access_token_properties.py`

  - [x] 3.9 Implement identity persistence tables and the auth-context query
    - `identity/adapters/outbound/persistence/tables.py`: SQLAlchemy Core `Table` objects for the identity tables (no `create_all`)
    - `identity/adapters/outbound/persistence/auth_context_repository.py`: one query joining `sessions` (`revoked_at IS NULL`), `users`, `role_assignments` effective at `now()` only when `users.account_status = 'active'`, and `role_permissions`, returning a `CurrentUser`; no cache
    - _Requirements: 2.11, 3.9, 5.4, 5.5, 5.6, 5.8_

  - [x] 3.10 Implement the auth dependencies (unblocks `market_data`)
    - `identity/adapters/inbound/http/deps.py`: `get_current_user` reading the `access_token` cookie name from `shared.infrastructure.cookies` (401 `NOT_AUTHENTICATED`), `require_permission(code)` (403 `FORBIDDEN`), `require_premium` (403 `PREMIUM_REQUIRED`), and `authenticate_access_token(token)` for the WebSocket handshake
    - Provide the token codec, clock and auth-context repository through `identity/composition.py`
    - _Requirements: 2.7, 2.11, 3.9, 4.9, 5.8, 5.9, 14.8_

  - [x]* 3.11 Write unit tests for the auth dependencies
    - Missing cookie, bad signature, expired token and revoked session return 401; missing permission returns 403 `FORBIDDEN`; a `pending_broker_activation` user gets 403 `FORBIDDEN`; non-premium returns 403 `PREMIUM_REQUIRED`
    - _Requirements: 2.11, 3.9, 5.9, 14.8_

- [x] 4. Registration (RF-01, RFP-02)
  - [x] 4.1 Implement registration validators, new-user mapping and default preferences
    - `identity/domain/validation.py`: pure validators for names, email syntax and `normalize_email`, E.164 phone, ISO 3166-1 alpha-2 country, password policy, interests (0-20, 1-50 chars), investor level, firm name (1-200 after trim) and license number (1-50 after trim); each returns the list of invalid fields
    - `identity/domain/registration.py`: `build_new_user(kind, payload)` for `investor`, `broker`, `administrator` that ignores any role value and returns the Account_Status and Role_Assignments: investor `active` + one `investor`; administrator `active` + one `administrator`; broker `pending_broker_activation` + none; optional-field defaults applied
    - `identity/domain/preferences.py`: the 7 event types, 4 channels and `default_preferences()` (28 pairs, only in_app enabled)
    - _Requirements: 1.2, 1.4, 1.5, 1.6, 2.1, 2.4, 2.9, 2.15, 7.1, 7.2, 7.3_

  - [x]* 4.2 Write property test for registration validation
    - **Property 1: Registration validation reports exactly the invalid fields**
    - **Validates: Requirements 1.1, 1.2, 1.4, 1.6, 1.7, 2.1, 2.4, 2.6, 2.9, 2.15**
    - File: `tests/identity/property/test_registration_properties.py`

  - [x]* 4.3 Write property test for email normalization
    - **Property 2: Email normalization makes duplicates case- and whitespace-insensitive**
    - **Validates: Requirements 1.5, 3.1**
    - File: `tests/identity/property/test_email_properties.py`

  - [x] 4.4 Write registration request schemas
    - `identity/adapters/inbound/http/schemas/auth.py`: `RegisterBaseIn`, `RegisterInvestorIn`, `RegisterBrokerIn` (+ `firm_name`, `license_number`) with `extra="ignore"`, `StrictBool`, `terms_accepted: Literal[True]`, field validators delegating to `identity.domain.validation`; `RegistrationOut {user_id, account_status}`
    - _Requirements: 1.1, 1.4, 1.6, 2.1, 2.4_

  - [x] 4.5 Implement the user repository and registration use cases
    - `identity/adapters/outbound/persistence/user_repository.py`: insert user (with `account_status`, firm name and license number), its Role_Assignments from `build_new_user` (none for brokers) and the 28 preferences in one transaction; unique violation on `email_normalized` becomes 409 `EMAIL_ALREADY_REGISTERED`
    - `identity/application/register.py`: `register_investor`, `register_broker`, `create_administrator`; role and status come from the registration type, never from input; password hashed with Argon2id
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.8, 1.9, 2.1, 2.2, 2.6, 2.9, 2.15, 7.3_

  - [x] 4.6 Add registration endpoints
    - `identity/adapters/inbound/http/routers/auth.py`: `POST /auth/register` (201 `{user_id, account_status: "active"}`), `POST /auth/register/broker` (201 `{user_id, account_status: "pending_broker_activation"}`)
    - `identity/adapters/inbound/http/routers/admin.py`: `POST /admin/users/administrators` (`admin:users`, 201 `{user_id, account_status: "active"}`)
    - Declare error responses with `error_responses`; responses never include the password or its hash; include routers in `identity/composition.py`
    - _Requirements: 1.1, 1.7, 2.1, 2.2, 2.3, 2.7, 2.9_

  - [x]* 4.7 Write API tests for registration
    - 201 paths with `account_status`; a `role` value in the body is ignored and a broker gets no Role_Assignment; 409 for case/whitespace duplicates; 422 naming each field; no password in any body; administrator creation 401/403
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.7, 2.15_

  - [x] 4.8 Write migration `0002_initial_admin` and the hash tool
    - `migrations/versions/0002_initial_admin.py` (revises `0001_identity_schema`): read `InitialAdminSettings`, fail naming each missing or invalid variable without values, validate with `identity.domain.validation`, require `$argon2id$` prefix, skip when `email_normalized` exists, otherwise insert user with `account_status = 'active'`, administrator Role_Assignment and 28 preferences with bound parameters; `downgrade()` is a no-op
    - `src/acciones_ud/shared/tools/hash_password.py`: prints an Argon2id hash for `INITIAL_ADMIN_PASSWORD_HASH`
    - _Requirements: 2.5, 2.8, 2.10, 7.3_

- [x] 5. Login, MFA and recovery codes (RF-02)
  - [x] 5.1 Implement TOTP window and MFA challenge rules
    - `identity/domain/totp_window.py`: `match(generator, code, t, last_step)` checks steps t-1, t, t+1, rejects steps `<= last_step` and non-6-digit codes, returns the matched step
    - `identity/domain/mfa.py`: challenge state transitions (expiry at 300 s, single use, invalidation after 5 failed attempts of either kind, TOTP or recovery code), the rule that a recovery code is refused while the TOTP enrollment is pending without counting as code use, and the `auth_events` result enum (including `invalid_recovery_code`)
    - _Requirements: 3.4, 3.6, 3.7, 3.10, 3.11, 18.5, 18.6_

  - [x] 5.2 Write property test for TOTP window and replay protection
    - **Property 4: TOTP window and replay protection**
    - **Validates: Requirements 3.4, 3.6, 3.11**
    - File: `tests/identity/property/test_totp_properties.py`

  - [x] 5.3 Write property test for the MFA challenge
    - **Property 5: MFA challenge attempt limit and single use**
    - **Validates: Requirements 3.6, 3.10, 18.5, 18.6**
    - File: `tests/identity/property/test_mfa_challenge_properties.py`

  - [x] 5.4 Implement recovery code rules
    - `identity/domain/recovery_codes.py`: `generate_set()` (10 distinct codes of 10 characters from `A-Z0-9` via `secrets.choice`, redraw on collision), `normalize(raw)` (trim, uppercase), `is_well_formed(code)` (`^[A-Z0-9]{10}$`), and helpers that hash a set and match a submitted code against unused hashes through the `PasswordHasher` port
    - _Requirements: 18.1, 18.3, 18.7, 18.9_

  - [x] 5.5 Write property test for recovery code sets
    - **Property 34: Recovery code sets are well formed and salted**
    - **Validates: Requirements 18.1, 18.7**
    - File: `tests/identity/property/test_recovery_code_properties.py` (`deadline=None`)

  - [x] 5.6 Implement the TOTP adapter and auth repositories
    - `identity/adapters/outbound/security/totp.py`: `pyotp` secret generation, otpauth URI (6 digits, 30 s), `TotpGenerator` implementation
    - Persistence: `mfa_repository.py` (insert, lock `FOR UPDATE`, attempts, invalidate, mark used), `auth_events_repository.py` (user agent truncated to 512, `method` column), `session_repository.py` (create session plus first refresh token), `recovery_code_repository.py` (insert a set under a new `set_id`, list unused codes of the current set, consume with `UPDATE ... WHERE id = $1 AND used_at IS NULL AND invalidated_at IS NULL RETURNING id`, count remaining, invalidate the current set, lock the user row `FOR UPDATE`)
    - _Requirements: 3.2, 3.3, 3.6, 3.7, 3.10, 18.1, 18.3, 18.7, 18.10_

  - [x] 5.7 Implement login and MFA verification use cases
    - `identity/application/login.py`: case-insensitive lookup, dummy-hash verify for unknown email, same `INVALID_CREDENTIALS` for both failures, pending encrypted TOTP secret when not enrolled, challenge issue, auth event
    - `identity/application/verify_mfa.py`: in one transaction lock the challenge; TOTP path: match the code, set `totp_last_step`, confirm a pending enrollment and insert 10 recovery code hashes, returning the plaintext codes once; recovery-code path: reject when the enrollment is pending, verify against unused codes of the current set, consume with the conditional update (a lost race counts as a failed attempt), return the remaining count; both paths count failures, invalidate at 5, create session and refresh token, mark the challenge used, record `auth_events` with `method`; DB failures give 503 with no tokens
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6, 3.7, 3.10, 3.12, 18.1, 18.3, 18.4, 18.5, 18.6, 18.10_

  - [x] 5.8 Implement recovery code regeneration
    - `identity/application/recovery_codes.py`: `regenerate_recovery_codes(current_user)`; 409 `MFA_NOT_ENROLLED` without a confirmed enrollment; otherwise in one transaction lock the user row, invalidate the current set, insert 10 new hashes and return the 10 plaintext codes
    - _Requirements: 18.7, 18.8_

  - [x] 5.9 Write property test for recovery code consumption
    - **Property 35: Recovery code consumption follows the reference model**
    - **Validates: Requirements 18.3, 18.5, 18.7**
    - File: `tests/identity/property/test_recovery_code_consumption_properties.py`, running the use cases of 5.7 and 5.8 against an in-memory `RecoveryCodeRepository` in `tests/support/identity_fakes.py` and a pure reference model (`deadline=None`)

  - [x] 5.10 Add login, MFA, current-user and recovery code endpoints
    - `schemas/auth.py`: `LoginIn`, `LoginOut`, `MfaVerifyIn {mfa_token, code?, recovery_code?}` with a model validator accepting exactly one of `code` (`^\d{6}$`) and `recovery_code` (trimmed, uppercased, `^[A-Z0-9]{10}$`), `MfaVerifyOut {user, recovery_codes, recovery_codes_remaining}`
    - `routers/auth.py`: `POST /auth/login`, `POST /auth/mfa/verify` (sets the `access_token` and `refresh_token` cookies with `set_auth_cookies`)
    - `schemas/users.py` and `routers/users.py`: `GET /users/me` with the 3.8 fields plus `account_status` and `mfa_enrolled` (valid access token, no permission), `POST /users/me/mfa/recovery-codes` (200 `{recovery_codes}`, 409 `MFA_NOT_ENROLLED`)
    - Wire in `identity/composition.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.8, 3.11, 18.1, 18.3, 18.7, 18.8, 18.9_

  - [x] 5.11 Write property test for MFA verification input
    - **Property 36: MFA verification input validation**
    - **Validates: Requirements 3.11, 18.9**
    - File: `tests/identity/property/test_mfa_input_properties.py` (targets `MfaVerifyIn`; a rejected body never reaches the challenge)

  - [x]* 5.12 Write API tests for login, MFA and recovery codes
    - No cookies on login; enrollment data only before confirmation; attributes of the `access_token` and `refresh_token` cookies; replayed code rejected; fifth failure invalidates the challenge; 422 does not consume an attempt; `auth_events` holds no password, code, recovery code or secret
    - Recovery codes: confirmation returns 10 codes once and `/users/me` and a later verify do not; recovery login returns `recovery_codes_remaining`; a used or previous-set code returns 401 `MFA_FAILED`; regeneration without enrollment returns 409 and stores nothing; captured logs contain no issued code
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6, 3.7, 3.8, 3.10, 3.11, 18.1, 18.2, 18.3, 18.4, 18.5, 18.7, 18.8_

- [x] 6. Sessions, refresh and logout (RFP-03)
  - [x] 6.1 Implement the Session_Service use cases
    - `identity/application/sessions.py` plus `session_repository.py` methods: atomic refresh `UPDATE ... RETURNING` with rotation, reuse detection that revokes the session, unknown-token path that changes nothing, list active sessions newest first with `current`, close one (404 `SESSION_NOT_FOUND`), close others with count, logout
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.10_

  - [x] 6.2 Add session endpoints
    - `routers/sessions.py`: `POST /auth/refresh` (200 `{access_expires_at, refresh_expires_at}`, new cookies through `set_auth_cookies`), `POST /auth/logout` (204), `GET /users/me/sessions`, `DELETE /users/me/sessions/{session_id}` (204), `POST /users/me/sessions/revoke-others` (200 `{revoked_count}`)
    - Use `clear_auth_cookies` on refresh failure, logout and closing the current session; wire in `identity/composition.py`
    - _Requirements: 4.1, 4.2, 4.4, 4.6, 4.8, 4.9_

  - [x]* 6.3 Write API tests for sessions
    - Rotation invalidates the old token; reuse revokes the session; ownership 404; revoke-others count; logout, current-session close and refresh failure clear both cookies
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

- [ ] 7. Checkpoint - Identity authentication core
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. RBAC administration and broker activation (RF-03, RFP-02)
  - [x] 8.1 Implement Role_Assignment validity validation
    - Add `validate_validity(valid_from, valid_to)` to `identity/domain/rbac.py` (offset required, `valid_to > valid_from`)
    - _Requirements: 5.2, 5.3_

  - [x]* 8.2 Write property test for Role_Assignment validity
    - **Property 8: Role assignment validity validation**
    - **Validates: Requirements 5.2, 5.3**
    - File: `tests/identity/property/test_role_validity_properties.py`

  - [x] 8.3 Implement the RBAC repository, administration and broker activation use cases
    - `persistence/rbac_repository.py` and `identity/application/rbac_admin.py`: list roles and permissions, add and remove role permissions, list/create/update/revoke assignments (last-administrator guard evaluated inside a locked transaction), set premium; 404 `NOT_FOUND` with `details.resource`; an `assignment_id` of another user is 404
    - `identity/application/broker_activation.py`: one transaction with `UPDATE users SET account_status = 'active' ... WHERE id = $1 AND account_status = 'pending_broker_activation' RETURNING id`, then insert the broker Role_Assignment (`valid_from = now()`, `valid_to` null); no row and the user exists gives 409 `BROKER_NOT_PENDING`, otherwise 404 `NOT_FOUND`
    - _Requirements: 2.12, 2.13, 2.14, 2.15, 5.2, 5.4, 5.5, 5.6, 5.7, 5.10, 5.11, 5.12_

  - [x] 8.4 Add administration endpoints
    - `schemas/admin.py` (`AwareDatetime`, `StrictBool` premium) and in `routers/admin.py`: `POST /admin/users/{user_id}/broker-activation` and `PUT /admin/users/{user_id}/premium` (`admin:users`); `GET`/`POST /admin/users/{user_id}/roles`, `PUT /admin/users/{user_id}/roles/{assignment_id}`, `POST /admin/users/{user_id}/roles/{assignment_id}/revoke`, `GET /admin/roles`, `GET /admin/permissions`, `POST /admin/roles/{role}/permissions`, `DELETE /admin/roles/{role}/permissions/{permission_code}` (`admin:rbac`); wire in `identity/composition.py`
    - _Requirements: 2.12, 2.13, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.9, 5.11, 5.12, 5.13_

  - [x]* 8.5 Write API tests for administration and broker activation
    - A change applies to the next request; 403 leaves data unchanged; 404 per resource; 409 `LAST_ADMINISTRATOR`; 422 for a non-boolean premium value
    - Broker: a pending broker gets 403 on `account:manage` endpoints; activation returns 200 with the broker assignment and the next request succeeds; activating an active user returns 409 `BROKER_NOT_PENDING` with no new assignment
    - _Requirements: 2.11, 2.12, 2.13, 5.2, 5.4, 5.5, 5.6, 5.9, 5.10, 5.11, 5.12, 5.13_

- [x] 9. Account preferences and settings (RF-07, RF-08, RF-09)
  - [x] 9.1 Implement preference merge and settings validators
    - `identity/domain/preferences.py`: `validate_patch(patch, has_phone, has_telegram)` and `merge(stored, patch)`
    - `identity/domain/settings.py`: portfolio view and order controls validators and the default constants
    - _Requirements: 7.2, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3_

  - [x]* 9.2 Write property test for preference merge round trip
    - **Property 10: Notification preference merge round trip**
    - **Validates: Requirements 7.2, 7.4, 7.7, 7.8**
    - File: `tests/identity/property/test_preferences_properties.py` (read-back half over the in-memory preference store)

  - [x]* 9.3 Write property test for rejected preference patches
    - **Property 11: Rejected preference patches change nothing**
    - **Validates: Requirements 7.5, 7.6**
    - File: `tests/identity/property/test_preference_rejection_properties.py`

  - [x]* 9.4 Write property test for settings validators
    - **Property 12: Settings validators accept exactly their domains**
    - **Validates: Requirements 8.1, 8.2, 9.1, 9.2**
    - File: `tests/identity/property/test_settings_properties.py`

  - [x] 9.5 Implement account settings repositories and use cases
    - Repositories for `notification_preferences`, `portfolio_view_settings`, `order_controls`, `users.telegram_chat_id`; use cases in `identity/application/` for get/put channel preferences (merge), set Telegram chat, get/put portfolio view and order controls (GET returns defaults without writing)
    - _Requirements: 7.4, 7.5, 7.8, 8.1, 8.3, 8.4, 9.1, 9.3, 9.4, 9.6_

  - [x] 9.6 Add account settings endpoints
    - `schemas/preferences.py` and `routers/preferences.py`, all with `account:manage`: `GET`/`PUT /users/preferences/channels` (PUT body lists 1 to 28 pairs, omitted pairs keep their value), `GET`/`PUT /users/preferences/portfolio`, `GET`/`PUT /users/preferences/orders`, `PUT /users/me/telegram`; wire in `identity/composition.py`
    - _Requirements: 7.4, 7.5, 7.6, 7.8, 7.9, 8.1, 8.2, 8.5, 9.1, 9.2, 9.5_

  - [x]* 9.7 Write API tests for account settings
    - Defaults are not stored; per-user isolation; 422 `CHANNEL_NOT_AVAILABLE`; rejected patch changes nothing; DB failure gives 503 and keeps stored values
    - _Requirements: 7.4, 7.5, 7.6, 7.8, 8.2, 8.3, 8.4, 9.2, 9.3, 9.4, 9.6_

- [x] 10. KYC, account information and interests (RFP-01, RF-06, RFP-08)
  - [x] 10.1 Implement KYC domain rules
    - `identity/domain/redaction.py`: `last4(tax_id)` and `redact(text, tax_id)` (removes the tax id and long digit runs, max 500 chars)
    - `identity/domain/kyc.py`: `can_trade(status)`, income and net worth range mapping to Alpaca min/max, reservation staleness (120 s)
    - _Requirements: 10.2, 10.5, 10.7_

  - [x] 10.2 Write property test for tax identifier redaction
    - **Property 13: Tax identifier never leaks**
    - **Validates: Requirements 10.2, 10.7**
    - File: `tests/identity/property/test_redaction_properties.py`

  - [x]* 10.3 Write property test for can_trade
    - **Property 14: can_trade follows the Alpaca status**
    - **Validates: Requirements 10.3, 10.5, 10.10, 10.11**
    - File: `tests/identity/property/test_kyc_properties.py`

  - [x] 10.4 Implement the Alpaca accounts client and fake
    - `identity/adapters/outbound/alpaca/accounts_client.py` (`POST /v1/accounts`, `GET /v1/accounts/{id}`, 400/409/422 as `AlpacaValidationError`) and `fake_accounts.py` (`FakeAlpacaAccounts`, scriptable outcomes, call recording)
    - _Requirements: 10.1, 10.4, 10.7, 10.9, 17.5, 17.6_

  - [x] 10.5 Implement KYC submission and status
    - `schemas/kyc.py` (`KycSubmissionIn`, date of birth before today, `customer_agreement` must be true), `identity/application/kyc.py` (reserve `kyc_accounts` row, 409 `KYC_ACCOUNT_EXISTS` without an Alpaca call, store last four only, nothing stored on Alpaca failure; status refresh with `stale` fallback; no Alpaca call without an account), `routers/kyc.py` with `POST /kyc/account` (201) and `GET /kyc/status` (`kyc:submit`); wire in `identity/composition.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11_

  - [x] 10.6 Extend `GET /users/me` with account information
    - `identity/application/account_info.py` and `routers/users.py`/`schemas/users.py`: complete `UserMeOut` (phone, country, `account_status`, `registered_at`, `contracted_plan` and `associated_broker` null, `kyc_status` from Alpaca only when an account is linked, 10 s timeout and `kyc_status_unavailable` fallback, `interests`, `investor_level`); read-only; still needs only a valid access token so a pending broker can read it
    - _Requirements: 3.8, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 10.7 Implement interests and level
    - `identity/domain/interests.py` (bounds, case-insensitive match, canonical form, first-occurrence dedup), `persistence/interest_catalog_repository.py` implementing `InterestCatalogPort` by reading `markets.code` and distinct `instruments.sector` (tables from revision 0003), `identity/application/interests.py`, and `PUT /users/me/interests` (`account:manage`) in `routers/users.py`; wire in `identity/composition.py`
    - _Requirements: 11.1, 11.2_

  - [x]* 10.8 Write property test for interest normalization
    - **Property 15: Interest normalization**
    - **Validates: Requirements 11.1, 11.2**
    - File: `tests/identity/property/test_interests_properties.py`

  - [x]* 10.9 Write API tests for KYC, account information and interests
    - Stored last four only; 409 and 422 without Alpaca calls; Alpaca 422/502/503 store nothing; status updated only on change; degraded `/users/me`; interests 422 keeps stored values
    - _Requirements: 6.1, 6.4, 6.5, 10.1, 10.2, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11, 11.1, 11.2_

- [ ] 11. Checkpoint - MOD-01 identity track complete
  - Ensure all tests pass, ask the user if questions arise.

### MOD-01 identity: readme_agregar.md gaps (owner: Daniel Sanabria)

Tasks 22-30 implement the `readme_agregar.md` gaps: Requirements 2.12-2.17 (D5), 4.6 and 4.11-4.14 (D10), 6 and 23 (D8), 20 and 21 (D7), 22 (D6), 24 (D9) and 25 (D11), with Assumptions A10-A14. They extend the finished identity code of tasks 3-10 and share no source file with the MOD-02 track. Every test uses in-memory fakes, `httpx.ASGITransport` and dependency overrides; none uses a `db` marker or connects to a database.

- [x] 22. Schema, settings and error codes for the readme_agregar.md gaps
  - [x] 22.1 Write migration `0005_identity_admin_gaps`
    - `migrations/versions/0005_identity_admin_gaps.py`, `revision = "0005_identity_admin_gaps"`, `down_revision = "0004_assignment_cancellation"` (never `0003_market_data_schema`, which would create a second head)
    - `upgrade()`: add `kyc_accounts.status_checked_at timestamptz null`; create `admin_audit_log` with the columns and checks of the design "Tables" row (the 11 action codes of 25.1, `target_type` in `user`/`role`, `target_id` 1-100 characters, `payload jsonb` object check, `actor_user_id` FK `users` without cascade) and the indexes (`occurred_at desc`, `id desc`), (`actor_user_id`), (`target_type`, `target_id`), (`action`); enable RLS on it with no policies; create the function `admin_audit_log_immutable()` and a `BEFORE UPDATE OR DELETE` row trigger that raises; create index `ix_users_created_at_id` on (`created_at desc`, `id`)
    - `downgrade()`: drop the trigger, the function, `admin_audit_log`, the index and the column
    - Applying it with `uv run alembic upgrade head` and checking it against Supabase (single head, `alembic current` is `0005_identity_admin_gaps`, the trigger rejects `UPDATE` and `DELETE`) is a manual developer step, not an automated test
    - _Requirements: 17.7, 20.1, 23.5, 25.2, 25.3, 25.14_

  - [x] 22.2 Add the new column and table to the identity table objects
    - `identity/adapters/outbound/persistence/tables.py`: `status_checked_at` on `kyc_accounts` and an `admin_audit_log` Core `Table` (`id`, `actor_user_id`, `action`, `target_type`, `target_id`, `payload` JSONB, `occurred_at`); no `create_all`
    - _Requirements: 23.5, 25.2_

  - [x] 22.3 Add the KYC status settings
    - `src/acciones_ud/config/settings.py`: `kyc_status_refresh_enabled: str = "false"`, `kyc_status_refresh_interval_seconds: str = "900"`, `kyc_status_cache_ttl_seconds: str = "60"`, plain strings like `price_staleness_threshold_seconds`
    - `require_api_settings` rejects by name only: an enabled flag whose lowercased value is not `true` or `false` (empty string included), an interval that is not a base-10 integer from 60 to 86,400, a TTL that is not a base-10 integer from 0 to 3,600; only an absent variable takes the default
    - Add `kyc_refresh_config(settings)` returning the parsed enabled flag, interval and TTL for `identity/composition.py`
    - Add the three variables with their defaults to `.env.example`
    - _Requirements: 17.8, 23.1, 23.12_

  - [x]* 22.4 Extend the property test for missing and invalid configuration
    - **Property 32: Missing configuration is reported by name only**
    - **Validates: Requirements 13.17, 17.3, 17.8, 23.12**
    - File: `tests/shared/property/test_config_properties.py`: generators add the three `KYC_STATUS_*` variables (absent takes the default, empty string invalid, other letter case of `true`/`false` accepted, non-integers and out-of-range integers rejected); the error names each invalid variable and contains no value
    - Example smoke test: the app refuses to start with an invalid `KYC_STATUS_*` value and `FakeAlpacaAccounts` records no call

  - [x] 22.5 Add the new error codes
    - `src/acciones_ud/shared/domain/errors.py`: add `KYC_RECONCILE_NOT_FOUND` (404), `KYC_RECONCILE_AMBIGUOUS` (409), `ALPACA_ACCOUNT_IN_USE` (409) and `KYC_SUBMISSION_IN_PROGRESS` (409) to `ErrorCode`
    - _Requirements: 24.3, 24.4, 24.7, 24.8_

  - Evidence: commit `b4f2446` (migration, table objects, settings, property test extension, offline render test).

- [x] 23. Logout with optional credentials (gap C1, P0)
  - [x] 23.1 Implement the logout target rule
    - `identity/domain/logout.py`: pure `target(access: AccessClaims | None, access_session_active: bool, refresh_digest: bytes | None)` deciding which Session to revoke (the access token's Session when valid and unrevoked, otherwise the Session of the matching refresh token, otherwise none) and the refresh-cookie shape check (43 URL-safe characters)
    - _Requirements: 4.6, 4.11, 4.12_

  - [x] 23.2 Add the logout repository methods
    - `identity/domain/auth_ports.py` and `persistence/auth_repository.py`: `revoke_if_active(user_id, session_id, now) -> bool` (`UPDATE sessions ... WHERE id = sid AND user_id = sub AND revoked_at IS NULL RETURNING id`) and `revoke_by_refresh_digest(digest, now) -> bool` (join on `refresh_tokens.token_hash`, no `rotated_at` or `expires_at` condition); the existing `revoke` stays unchanged
    - In-memory versions in `tests/support/identity_fakes.py`, scriptable to raise `AppError(503, DATABASE_UNAVAILABLE)`
    - _Requirements: 4.6, 4.11, 4.12, 4.14_

  - [x] 23.3 Rework the logout use case and endpoint
    - `identity/application/sessions.py`: `SessionService.logout(access_token, refresh_token)` in one unit of work; the access step runs first and the refresh step only when the access step revoked nothing, so a refresh cookie never revokes a second Session
    - `routers/sessions.py`: `POST /auth/logout` no longer declares `get_current_user`; it reads both cookies through `APIKeyCookie(auto_error=False)`, returns 204 with `clear_auth_cookies` for every credential state and never 401; on `AppError` `DATABASE_UNAVAILABLE` it builds the Error_Body response with the shared builder of `shared/infrastructure/http_errors.py` (expose it if needed), clears both cookies on it and returns 503
    - OpenAPI documents 204 and 503 only, with both cookie schemes optional
    - _Requirements: 4.6, 4.11, 4.12, 4.13, 4.14_

  - [x] 23.4 Write property test for logout
    - **Property 44: Logout always clears both cookies and revokes exactly the reference Session**
    - **Validates: Requirements 4.6, 4.11, 4.12, 4.13, 4.14**
    - File: `tests/identity/property/test_logout_properties.py`, through `httpx.ASGITransport` with the in-memory session store override (`deadline=None`)

  - [x]* 23.5 Write API tests for logout
    - Expired access token with a valid refresh cookie revokes that Session and returns 204 (the gap C1 case); a valid access token with another Session's refresh cookie revokes only the access token's Session; no cookies returns 204 with both cookies cleared; an unknown refresh hash changes nothing; 503 still clears both cookies and changes no Session; a refresh after logout returns 401 `REFRESH_INVALID`
    - _Requirements: 4.2, 4.6, 4.11, 4.12, 4.13, 4.14_

  - Evidence: commit `4a10d30` (domain rule, repository methods, use case, router, shared error body, Property 44 and API tests).

- [x] 24. Broker activation with the investor role and the broker request flag (gaps A3, D1)
  - [x] 24.1 Implement BrokerActivationService
    - `identity/application/broker_activation.py`: `BrokerActivationService.activate(actor_id, user_id)` replaces `RbacService.activate` in `rbac_admin.py`; one unit of work with the conditional `UPDATE users SET account_status = 'active' ... WHERE id = $1 AND account_status = 'pending_broker_activation' RETURNING id`, then a broker and an investor Role_Assignment through `RbacRepository.save_assignment` with the same `$now` from the `Clock` port and `valid_to` null; no row and the user exists gives 409 `BROKER_NOT_PENDING`, otherwise 404 `NOT_FOUND`; the RBAC seed is unchanged
    - `schemas/admin.py`: `BrokerActivationOut {user_id, account_status, role_assignment, investor_assignment}` (`role_assignment` stays the broker assignment)
    - `routers/admin.py`: `POST /admin/users/{user_id}/broker-activation` calls the new service (the administrator-role check stays); wire it in `identity/composition.py`; the Audit_Entry is added in task 28.4
    - _Requirements: 2.12, 2.13, 2.14, 2.16, 2.17, 22.7_

  - [x]* 24.2 Write tests for broker activation
    - Activation returns 200 with `role_assignment` (broker) and `investor_assignment`, and the next request holds `kyc:submit`; an active User with the Broker_Request_Flag true or false gets 409 `BROKER_NOT_PENDING` and no new assignment; a fake that fails the second insert leaves the User pending with no assignment and returns 503; unknown user 404; a requester with `admin:users` but no administrator role gets 403
    - _Requirements: 2.3, 2.12, 2.13, 2.16, 2.17, 22.7_

  - [x] 24.3 Return the broker request flag in account information
    - `identity/application/account_info.py` reads `users.broker_requested`; `schemas/users.py` adds `broker_requested: bool` (never null) to `UserMeOut`
    - Check that no request schema other than investor registration declares `broker_requested` and that all keep `extra="ignore"`, so no later request changes the flag
    - _Requirements: 22.1, 22.2, 22.8_

  - [x]* 24.4 Write API tests for the broker request flag
    - `/users/me` returns `broker_requested` true or false, false when the registration omitted it; assigning the broker role through `POST /admin/users/{user_id}/roles` keeps the flag, the investor assignment and the Account_Status; a requester with `admin:rbac` but no administrator role gets 403 and nothing is stored; a `broker_requested` field in other request bodies is ignored; a non-boolean flag at registration returns 422
    - _Requirements: 22.1, 22.2, 22.4, 22.5, 22.6, 22.8, 22.9_

  - Evidence: commit `0f3059d` (BrokerActivationService, both assignments, `broker_requested` in `/users/me`, tests updated).

- [x] 25. Administrative user directory with KYC data (gaps A1, A2)
  - [x] 25.1 Implement the directory domain rules
    - `identity/domain/directory.py`: `DirectoryQuery` (filters, `limit` 50, `offset` 0), `KYC_STATUSES` (the 11 values of 21.6), `DirectoryEntry` with exactly the fields of 20.2 and 21.1 and no field for any hash, secret or `tax_id_last4`, `kyc_fields(row)` deriving `kyc_link_state` and the nulls of 21.2 and 21.3, `like_pattern(q)` escaping `\`, `%` and `_`, and `select(users, query, now)` as the executable specification of filtering, ordering (`registered_at` descending, `user_id` ascending) and paging
    - _Requirements: 20.2, 20.3, 20.5, 20.8, 21.1, 21.2, 21.3, 21.4, 21.5_

  - [x]* 25.2 Write property test for the q pattern
    - **Property 41: The q pattern matches literally**
    - **Validates: Requirements 20.8**
    - File: `tests/identity/property/test_directory_pattern_properties.py`

  - [x]* 25.3 Write property test for the KYC fields
    - **Property 42: KYC_Link_State and KYC fields are derived from the stored row**
    - **Validates: Requirements 21.1, 21.2, 21.3, 21.4, 21.5**
    - File: `tests/identity/property/test_directory_kyc_properties.py`

  - [x] 25.4 Implement the shared effective-assignment expression and the directory repository
    - `persistence/tables.py`: `effective_assignment(ra, users, now)` = `users.account_status = 'active' AND ra.status = 'ACTIVE' AND ra.valid_from <= now AND (ra.valid_to IS NULL OR now < ra.valid_to)`; switch `auth_context_repository.py` to it with no behavior change
    - `identity/domain/admin_ports.py`: `UserDirectoryRepository.search(query, now) -> DirectoryPage(items, total)` and `.get(user_id, now) -> DirectoryEntry | None`
    - `persistence/user_directory_repository.py`: one CTE statement per call built with SQLAlchemy Core (each filter added only when supplied, explicit select list that never reads `password_hash` or `totp_secret_enc`, roles from `effective_assignment`, `LEFT JOIN` of the count row so `total` survives `offset >= total`); `get` reuses the filtered select
    - In-memory fake in `tests/support/identity_fakes.py` that applies `directory.select`
    - _Requirements: 2.11, 20.1, 20.2, 20.3, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 21.6, 21.7, 21.9_

  - [x] 25.5 Implement the User_Directory_Service
    - `identity/application/user_directory.py`: `UserDirectoryService.list(query)` and `.detail(user_id)` in one unit of work; a missing user raises 404 `NOT_FOUND` with `details.resource = "user"`; no write, no Audit_Entry and no Alpaca port
    - _Requirements: 20.1, 20.12, 20.13, 20.15, 20.18, 21.5_

  - [ ]* 25.6 Write property test for the directory listing
    - **Property 40: User directory listing matches a reference model**
    - **Validates: Requirements 20.1, 20.2, 20.4, 20.5, 20.6, 20.7, 20.9, 20.10, 21.6, 21.7, 21.9, 22.3**
    - File: `tests/identity/property/test_directory_properties.py`, running the use case over the in-memory directory fake against a reference model written in the test module

  - [x] 25.7 Add the directory endpoints
    - `schemas/admin.py`: `UserDirectoryQueryIn` (`account_status`, `role`, `kyc_status` and `kyc_link_state` as case-sensitive `Literal`s, `q` trimmed 1-100 with whitespace-only rejected, `broker_requested` as `Literal["true","false"]` converted to `bool`, `limit` 1-100 default 50, `offset` ≥ 0 default 0), `UserDirectoryEntryOut`, `UserDirectoryPageOut {items, total, limit, offset}` echoing the applied values
    - `routers/admin.py`: `GET /admin/users` (`Annotated[UserDirectoryQueryIn, Query()]`) and `GET /admin/users/{user_id}` (`user_id: UUID`), both with `require_permission("admin:users")` so 401 and 403 come before parameter validation; wire in `identity/composition.py`
    - _Requirements: 20.1, 20.4, 20.11, 20.12, 20.14, 20.16, 20.17, 21.8, 22.3_

  - [x]* 25.8 Write API tests for the directory
    - Detail returns the entry; unknown UUID 404, non-UUID 422; unauthenticated and invalid gets 401, unprivileged and invalid gets 403; no write, no Audit_Entry and no Alpaca call; the entry JSON holds no hash, secret or `tax_id_last4`; a pending broker shows `roles = []`; a fake raising `DATABASE_UNAVAILABLE` gives 503 with no partial body
    - _Requirements: 20.2, 20.3, 20.12, 20.13, 20.14, 20.15, 20.16, 20.17, 20.18_

  - Evidence: commit `b186c83` (pure directory rules, shared effective-assignment predicate, CTE repository, endpoints, Properties 41/42 and API tests).

- [x] 26. KYC status cache and KYC_Refresh_Job (gap B3)
  - [x] 26.1 Implement the KYC cache rules
    - `identity/domain/kyc_cache.py`: `KycStatusState`, `serve_cached(checked_at, now, ttl_seconds)` (true only when TTL > 0, `checked_at` not null and `now - checked_at <= ttl`; a future `checked_at` counts as fresh), `apply_status_check(stored, retrieved, retrieved_at)` (None when the stored check is later; otherwise sets `checked_at` and changes `status` and `status_updated_at` only on a different status), and `cycle_action(outcome)` (store, skip, end cycle)
    - _Requirements: 23.4, 23.5, 23.6, 23.7, 23.8, 23.9_

  - [x]* 26.2 Write property test for status checks
    - **Property 46: Status checks never move backwards and failures change nothing**
    - **Validates: Requirements 6.5, 23.5, 23.10**
    - File: `tests/identity/property/test_kyc_status_check_properties.py`

  - [x] 26.3 Replace `update_status` with `record_status_check`
    - `identity/domain/kyc_ports.py` and `persistence/kyc_repository.py`: `record_status_check(account, retrieved_at)` keyed on `alpaca_account_id` only, one `UPDATE` with the `status_checked_at IS NULL OR status_checked_at <= $retrieved_at` guard and the `CASE` on `status_updated_at`; it never inserts a row or changes `alpaca_account_id`; add `linked_account_ids()`
    - `identity/application/kyc.py`: `KycService.status` keeps asking Alpaca and stores `status_checked_at` through `record_status_check`
    - In-memory versions in `tests/support/identity_fakes.py` that apply `apply_status_check`
    - _Requirements: 10.4, 23.5, 23.10_

  - [x] 26.4 Add the KYC status cache to account information
    - `identity/application/account_info.py`: `AccountInfoService` gains `cache_ttl_seconds`; one unit of work reads the user and KYC rows (503 before any Alpaca call); none or unlinked gives `kyc_status = null` with no call; linked and `serve_cached` returns the stored status with no call; otherwise `get_account` (10 s), where `AlpacaError` gives `kyc_status_unavailable = true` with no write, and success calls `record_status_check` in a new unit of work whose `DATABASE_UNAVAILABLE` is logged without values and swallowed
    - `identity/composition.py`: `account_info_service(request)` passes the TTL parsed by `kyc_refresh_config`
    - _Requirements: 6.1, 6.4, 6.5, 6.6, 23.4, 23.6, 23.11_

  - [x]* 26.5 Write property test for the cache decision
    - **Property 45: KYC status cache freshness decision**
    - **Validates: Requirements 6.4, 23.4, 23.6**
    - File: `tests/identity/property/test_kyc_cache_properties.py` (pure `serve_cached` and the account information use case over fakes, asserting when `FakeAlpacaAccounts` is called)

  - [x] 26.6 Implement the KYC_Refresh_Job and its lifecycle
    - `identity/adapters/inbound/jobs/__init__.py` and `kyc_refresh_job.py`: `KycRefreshJob(accounts, uow, clock, interval_seconds)` with `start`, `stop`, `run`, `run_cycle` following `market_data/adapters/inbound/jobs/clock_watcher.py`; first cycle one interval after start; next sleep starts after the cycle ends; snapshot of `linked_account_ids()` at cycle start; 429 ends the cycle, other `AlpacaError` skips the account, one transaction per stored account; no new request once stopping; per-cycle exceptions logged without ids or values; `stop()` sets the event and waits at most 10 s, then cancels
    - `identity/composition.py`: `startup(app)` builds and starts the job with `AlpacaAccountsClient(app.state.alpaca_broker)` when enabled and stores it in `app.state.kyc_refresh_job`; `shutdown(app)` awaits `job.stop()` before disposing the engine
    - `main.py`: enter the Alpaca broker client into the `AsyncExitStack` before pushing `identity.shutdown`, so the job stops before the client closes
    - _Requirements: 23.2, 23.3, 23.7, 23.8, 23.9, 23.10, 23.13, 23.14_

  - [x]* 26.7 Write property test for a refresh cycle
    - **Property 47: A KYC_Refresh_Job cycle follows its outcome script**
    - **Validates: Requirements 23.2, 23.7, 23.8, 23.9, 23.10**
    - File: `tests/identity/property/test_kyc_refresh_job_properties.py`, with `FakeAlpacaAccounts` and an in-memory KYC store

  - [x]* 26.8 Write tests for the cache and the job
    - No Alpaca call for none or unlinked; database failure before the Alpaca call gives 503 with no call; a failing store after retrieval still returns the retrieved status with `kyc_status_unavailable = false`; with a fake sleep, the first cycle starts one interval after startup and the next one interval after the previous ends; a disabled flag starts no job; `stop()` during an in-flight fake request waits up to 10 s, then cancels without a write
    - _Requirements: 6.4, 6.5, 6.6, 23.2, 23.3, 23.11, 23.13, 23.14_

  - Evidence: commit `4feacea` (cache rules, monotonic status check, account-info cache, refresh job and lifecycle, Properties 45/46/47 and job tests).

- [x] 27. KYC reconciliation (gap B4)
  - [x] 27.1 Add the account list to the Alpaca accounts port, client and fake
    - `identity/domain/kyc.py`: `AlpacaAccountSummary {id, status, updated_at, contact_email}`; `identity/domain/kyc_ports.py`: `AlpacaAccountsPort.list_accounts(query, timeout=10)`, and `get_account` documents 404 as `AlpacaNotFound`
    - `alpaca/accounts_client.py`: `list_accounts` calls `GET /v1/accounts?query=<email>&entities=contact` and maps `contact.email_address`, errors through `classify` and `raise_for_alpaca`; `get_account` raises `AlpacaNotFound` on 404
    - `alpaca/fake_accounts.py`: scripted `list_accounts` with call recording
    - _Requirements: 24.1, 24.2, 24.3, 17.5, 17.6_

  - [x] 27.2 Implement the reconciliation decision rules and error mapping
    - `identity/domain/kyc_reconcile.py`: `precheck(state, supplied, now)` following the design decision table (`AlreadyLinked`, `KYC_ACCOUNT_EXISTS`, `KYC_SUBMISSION_IN_PROGRESS` under 120 s, `LookupById`, `SearchByEmail`, identifiers compared as `UUID`), `pick_candidate(accounts, registered_email)` (trimmed, lowercased contact email: `Found`, `NotFound`, `Ambiguous(count)`), and `reconcile_alpaca_error(exc) -> AppError` (`AlpacaNotFound` 404 `KYC_RECONCILE_NOT_FOUND`, `AlpacaUnavailable` 502, `AlpacaRateLimited` 503, `AlpacaAuthError` and `AlpacaValidationError` 500 `INTERNAL_ERROR`; never `to_app_error`, never `SYMBOL_NOT_FOUND`)
    - _Requirements: 24.2, 24.3, 24.4, 24.5, 24.6, 24.8, 24.9_

  - [x] 27.3 Add the reconciliation repository methods
    - `identity/domain/kyc_ports.py` and `persistence/kyc_repository.py`: `get_by_alpaca_id(account_id)`, `link_new(...)` (`INSERT ... ON CONFLICT DO NOTHING RETURNING user_id`, `tax_id_last4` null), `link_reserved(...)` (`UPDATE ... WHERE alpaca_account_id IS NULL AND reserved_at = $observed RETURNING user_id` inside `session.begin_nested()`, a unique violation becomes 409 `ALPACA_ACCOUNT_IN_USE`, `tax_id_last4` not in the `SET` list); identifiers stored as canonical lowercase UUID text
    - In-memory versions in `tests/support/identity_fakes.py`
    - _Requirements: 24.1, 24.7, 24.10, 24.12_

  - [x] 27.4 Implement KycReconcileService
    - `identity/application/kyc_reconcile.py`: `KycReconcileService.reconcile(actor_id, user_id, alpaca_account_id)`; unit of work 1 reads the user (404 `NOT_FOUND`) and the KYC row and runs `precheck`; the Alpaca call runs outside any transaction; unit of work 2 checks the in-use identifier, writes with `retrieved_at = clock.now()` and, when the write matches no row, re-reads and re-applies `precheck`; database failures give 503 with no change; tax identifiers never reach the response, an Error_Body or a log; the `kyc_reconciled` Audit_Entry is added in task 28.4
    - _Requirements: 24.1, 24.2, 24.5, 24.7, 24.9, 24.10, 24.11, 24.12, 24.13_

  - [x] 27.5 Add the reconciliation endpoint
    - `schemas/kyc.py`: `KycReconcileIn {alpaca_account_id: UUID | None = None}` and `KycReconcileOut {user_id, alpaca_account_id, status, outcome}`
    - `routers/admin.py`: `POST /admin/kyc/{user_id}/reconcile` with `require_permission("admin:users")`, `user_id: UUID` and `Body(default=None)` so an absent body, `{}` and a null value all search by email; a non-UUID is 422 before any Alpaca call; wire in `identity/composition.py`
    - _Requirements: 24.1, 24.2, 24.13, 24.14_

  - [x] 27.6 Write property test for reconciliation
    - **Property 48: Reconciliation follows the decision table**
    - **Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8, 24.9, 24.10, 24.11**
    - File: `tests/identity/property/test_kyc_reconcile_properties.py`, running the use case over `FakeAlpacaAccounts` and the in-memory KYC store against a reference table written in the test module

  - [x]* 27.7 Write API tests for reconciliation
    - Unknown user 404 `NOT_FOUND` and invalid UUIDs (path or body) 422, both with no Alpaca call; 401 and 403 store nothing and send no Alpaca request; the response, Error_Body and captured logs hold no tax identifier
    - _Requirements: 24.10, 24.13, 24.14_

  - Evidence: commit `2832ed5` (account list port/client/fake, decision table, repository writes, service, endpoint, Property 48 and API tests).

- [x] 28. Audit log of identity administrative actions (gap D3)
  - [x] 28.1 Implement the audit domain rules
    - `identity/domain/audit.py`: `AuditAction` (`StrEnum` of the 11 codes of 25.1), `AuditEntry` (frozen dataclass), `PAYLOAD_KEYS` per action and `build_entry(...)` that raises `ValueError` on a missing or extra payload key and serializes UUID and datetime values to ISO strings (`valid_to` null when open-ended)
    - _Requirements: 25.1, 25.2, 25.6_

  - [x] 28.2 Write property test for audit payloads
    - **Property 49: Audit payloads hold exactly the whitelisted keys**
    - **Validates: Requirements 25.1, 25.6**
    - File: `tests/identity/property/test_audit_payload_properties.py`

  - [x] 28.3 Implement the audit log repository and unit-of-work wiring
    - `identity/domain/admin_ports.py`: `AuditLogRepository.append(entry)` and `.search(query) -> AuditPage(items, total)`; no update or delete method
    - `persistence/audit_log_repository.py`: `append` and a `search` CTE ordered by `occurred_at DESC, id DESC` with exact, case-sensitive equality filters; a failing `append` raises 503 `DATABASE_UNAVAILABLE`
    - `AdminWork`, the identity unit of work used by registration and the reconciliation unit of work gain an `audit` attribute bound to the same `AsyncSession` (wired in `identity/composition.py`)
    - In-memory audit fake and a unit-of-work fake in `tests/support/identity_fakes.py` that buffer writes and commit only when the block exits without an exception, scriptable to fail `append`
    - _Requirements: 25.3, 25.4, 25.9, 25.14_

  - [x] 28.4 Write Audit_Entries from every administrative use case
    - `rbac_admin.py`: `premium_changed`, `role_assignment_created`, `role_assignment_updated` (with the previous validity), `role_assignment_revoked`, `role_assignment_cancelled` (also for the 200 on an already cancelled assignment), `role_permission_added`, `role_permission_removed`
    - `broker_activation.py`: `broker_activated` with both assignment ids; `register.py`: `RegistrationService.create_administrator(payload, actor_id)` writes `administrator_created` (the router passes the actor); `kyc_reconcile.py`: `kyc_reconciled` with `outcome` `linked` or `already_linked`
    - Each writer calls `append` as the last step inside the same `unit_of_work` as the change, with `actor_user_id` from `CurrentUser.user_id` and `occurred_at` equal to the use case's `now`; an earlier `AppError` stores no entry
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_

  - [x] 28.5 Write property test for audit atomicity
    - **Property 50: Audit entries are atomic with their administrative change**
    - **Validates: Requirements 25.1, 25.2, 25.3, 25.4, 25.5**
    - File: `tests/identity/property/test_audit_atomicity_properties.py`, over the in-memory unit-of-work fake with scripted successes, early `AppError`s and failing appends

  - [x] 28.6 Add the audit log read endpoint
    - `identity/application/audit_log.py`: `AuditLogService.list(query)` (read-only)
    - `schemas/admin.py`: `AuditLogQueryIn` (`action` `Literal` of the 11 codes, `actor_user_id` UUID, `target_type` `user`/`role`, `target_id` 1-100, `limit` 1-100 default 50, `offset` ≥ 0 default 0), `AuditEntryOut`, `AuditLogPageOut {items, total, limit, offset}`
    - `routers/admin.py`: `GET /admin/audit-log` with `require_permission("admin:rbac")`; no endpoint creates, updates or deletes an Audit_Entry; wire in `identity/composition.py`
    - _Requirements: 25.7, 25.8, 25.9, 25.10, 25.11, 25.12, 25.13_

  - [x]* 28.7 Write property test for the audit log listing
    - **Property 51: Audit log listing matches a reference model**
    - **Validates: Requirements 25.7, 25.8, 25.9, 25.14**
    - File: `tests/identity/property/test_audit_log_properties.py`, over the in-memory audit fake

  - [x]* 28.8 Write property test for admin listing parameters
    - **Property 43: Admin listing parameters are validated together**
    - **Validates: Requirements 20.4, 20.11, 21.8, 25.8, 25.10**
    - File: `tests/identity/property/test_admin_query_properties.py`, targeting `UserDirectoryQueryIn` and `AuditLogQueryIn` through `httpx.ASGITransport` with the use cases overridden

  - [x]* 28.9 Write API tests for the audit log
    - `occurred_at` lies between request receipt and response; a failed administrative request (404, 409, 422) stores no entry; 401 and 403 return no entries; a failing `append` returns 503 and leaves the change unstored
    - _Requirements: 25.2, 25.4, 25.5, 25.11, 25.13_

  - Evidence: commit `91b6e5b` (audit domain, repository, entries from every writer, read endpoint, Properties 49/50/51, API tests).

- [x] 29. OpenAPI contract for the readme_agregar.md endpoints
  - [x] 29.1 Declare the error responses of the new and changed operations
    - With `error_responses`, as in task 20.1: `GET /admin/users` (401, 403, 422, 503), `GET /admin/users/{user_id}` (401, 403, 404, 422, 503), `POST /admin/users/{user_id}/broker-activation` (401, 403, 404, 409, 422, 503), `POST /admin/kyc/{user_id}/reconcile` (401, 403, 404, 409, 422, 500, 502, 503), `GET /admin/audit-log` (401, 403, 422, 503), and `POST /auth/logout` with 204 and 503 only (no 401)
    - _Requirements: 4.14, 17.1, 17.2, 25.12_

  - [x]* 29.2 Extend the OpenAPI contract tests
    - The paths match the design endpoint table, including `/admin/users`, `/admin/users/{user_id}`, `/admin/kyc/{user_id}/reconcile` and `/admin/audit-log`; every new operation lists its errors with the `ErrorBody` schema; logout declares no 401 and both cookie schemes as optional; no operation creates, updates or deletes an Audit_Entry
    - _Requirements: 4.14, 17.1, 17.2, 25.12_

  - Evidence: commit `91b6e5b` (logout security includes the no-credentials alternative; contract tests cover the new paths).

- [x] 30. Checkpoint - readme_agregar.md gaps complete
  - Ensure all tests pass, ask the user if questions arise.
  - Evidence: `ruff`, `mypy` and `pytest` green (280 passed, 18 DB-marked tests skipped without `TEST_DATABASE_URL`).

### MOD-02 market_data track (owner: Davidson Sánchez)

- [ ] 12. Market data schema, domain contracts and symbol validation
  - [x] 12.1 Write migration `0003_market_data_schema`
    - `migrations/versions/0003_market_data_schema.py`, `revision = "0003_market_data_schema"`, `down_revision = "0002_initial_admin"`
    - Create `markets`, `schedule_overrides`, `instruments`, `catalog_state`, `instrument_snapshots` (with `quote_updated_at` and the `feed` check in `iex`, `sip`, `delayed_sip`), `market_clock_state`, `watchlists`, `watchlist_items`, `price_alerts`, `notifications`, `notification_deliveries` with every constraint and index of the design; enable RLS on each; seed the Market codes and the `catalog_state` and `market_clock_state` rows (`id = 1`)
    - `downgrade()` drops the tables in reverse foreign-key order
    - _Requirements: 12.3, 13.6, 13.14, 14.1, 15.7, 17.7_

  - [x] 12.2 Define market_data domain entities and ports
    - `market_data/domain/entities.py`: `Instrument`, `Market`, `ScheduleOverride`, `Snapshot` (with feed), `StoredSnapshot`, `Freshness`, `LatestQuoteDoc` (optional keys kept as `None`), `DepthLevel`, `DepthResult`, `Bar`, `BarsPage`, `CalendarDay`, `Clock` value, `Watchlist`, `PriceAlert`, `Notification`, `Recipient`
    - `market_data/domain/ports.py`: `AlpacaBrokerMarketPort`, `AlpacaDataPort` (including `get_latest_quote`), `StreamUpstreamPort`, repository Protocols, `RecipientDirectory`, `UserProfileReader`, `ChannelSender`
    - _Requirements: 12.2, 13.1, 13.11, 14.4, 15.1, 19.1_

  - [x] 12.3 Implement symbol validation
    - `market_data/domain/symbols.py`: `validate_symbol(raw)` (trim, 1-20 chars, `^[A-Za-z0-9./-]+$`, uppercase)
    - _Requirements: 16.1, 16.4, 19.6_

  - [ ]* 12.4 Write property test for symbol validation
    - **Property 22: Symbol path validation**
    - **Validates: Requirements 16.1, 16.4**
    - File: `tests/market_data/property/test_symbol_properties.py`

- [ ] 13. Catalog, search, markets list and asset detail (RF-24, RF-28)
  - [x] 13.1 Implement catalog merge and search ranking rules
    - `market_data/domain/catalog_merge.py`: merge fetched assets into the cache (listed flags, Alpaca fields overwrite, sector kept, null sector for new symbols, duplicate symbol keeps the `active` or first asset), single-asset merge
    - `market_data/domain/search.py`: query normalization, classification, rank group function used by the reference model and the SQL ordering
    - _Requirements: 12.1, 12.2, 12.5, 12.7, 16.2_

  - [ ]* 13.2 Write property test for catalog merge
    - **Property 18: Catalog merge preserves sectors**
    - **Validates: Requirements 12.5, 12.7, 16.2**
    - File: `tests/market_data/property/test_catalog_merge_properties.py`

  - [x] 13.3 Implement the Alpaca Broker market client and fake
    - `market_data/adapters/outbound/alpaca/broker_client.py` (`GET /v1/assets?asset_class=us_equity`, `/v1/assets/{symbol}` with 404 as `AlpacaNotFound`, `/v1/calendar`, `/v1/clock`) and `fake_broker.py` (`FakeAlpacaBrokerMarket`, scriptable, call recording)
    - _Requirements: 12.5, 15.1, 15.2, 16.1, 16.3, 17.5, 17.6_

  - [x] 13.4 Implement market_data persistence tables and the instrument repository
    - `market_data/adapters/outbound/persistence/tables.py`: Core `Table` objects for every market_data table
    - `instrument_repository.py`: search with escaped `LIKE`, rank ordering, 50-item pages and total; listed-only exchange list; catalog upsert with `listed` flags and unknown exchange insert; single-instrument upsert keeping sector; `catalog_state` read and update
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 16.2_

  - [x] 13.5 Implement catalog, search, markets list and asset detail use cases
    - `market_data/application/catalog.py` (`ensure_fresh` on age > `CATALOG_MAX_AGE_HOURS` or empty cache, fallback to cache on failure, 502/503 only with empty cache, `exists(symbol)`), `search.py`, `exchanges.py`, `asset_detail.py` (no write on Alpaca failure, 500 and unchanged row on write failure)
    - _Requirements: 12.1, 12.3, 12.4, 12.5, 12.8, 12.9, 16.1, 16.2, 16.3, 16.5, 16.6_

  - [x] 13.6 Add instrument and markets list endpoints
    - `market_data/adapters/inbound/http/schemas/instruments.py` and `routers/instruments.py`: `GET /instruments/search` and `GET /instruments/{symbol:path}` (registered after `/instruments/search`; later suffix routes are registered before it); `routers/markets.py`: `GET /markets`; all with `market:read` from `identity.adapters.inbound.http.deps`; wire in `market_data/composition.py`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.6, 16.1, 16.4_

  - [ ]* 13.7 Write property test for search over the in-memory instrument fake
    - **Property 17: Search matches a reference model**
    - **Validates: Requirements 12.1, 12.2, 12.4**
    - File: `tests/market_data/property/test_search_properties.py`; runs the search use case over an in-memory instrument repository fake in `tests/support/market_fakes.py` and compares with a reference model written in the test module; no database connection

  - [ ]* 13.8 Write API tests for instruments
    - Reload on age and on empty cache; cache fallback keeps the reload timestamp; 502/503 with empty cache; 404 unknown asset with no write; 422 symbol with no Alpaca call; a symbol containing `/` reaches the validator instead of a routing 404; 500 on write failure leaves the cached row; tests override identity deps with `dependency_overrides`
    - _Requirements: 12.3, 12.5, 12.6, 12.8, 12.9, 16.3, 16.4, 16.5, 16.6_

- [ ] 14. Quotes, candles, freshness, depth and price streaming (RF-25)
  - [x] 14.1 Implement price freshness rules
    - `market_data/domain/freshness.py`: `annotate(asset_class, feed, as_of, now, threshold_seconds, served_from_cache) -> Freshness` (`currency` `USD` only for `us_equity`, `source` `alpaca`, `data_age_seconds = max(0, floor(now - as_of))` or null, `is_delayed` only for `delayed_sip`, `is_stale` when served from cache, age null, or age above threshold) and `candle_meta(...)` returning the `currency`, `source`, `feed`, `is_delayed` subset
    - _Requirements: 13.11, 13.12, 13.13, 13.16_

  - [ ]* 14.2 Write property test for freshness fields
    - **Property 37: Freshness fields follow their formulas**
    - **Validates: Requirements 13.11, 13.12, 13.13, 13.16**
    - File: `tests/market_data/property/test_freshness_properties.py`

  - [x] 14.3 Implement quote and candle rules
    - `market_data/domain/quotes.py`: snapshot document mapping (nulls for omitted fields, later of quote and trade timestamps in UTC) and the pure `quote_outcome(live, stored)` decision (live, cached, or 502/503 error)
    - `market_data/domain/bars.py`: request validation naming every invalid parameter (date-only `end` means end of day UTC) and bar mapping (range filter, ascending, page size cap)
    - _Requirements: 13.1, 13.2, 13.4, 13.14, 13.15_

  - [ ]* 14.4 Write property test for snapshot mapping
    - **Property 19: Snapshot mapping**
    - **Validates: Requirements 13.1**
    - File: `tests/market_data/property/test_quotes_properties.py`

  - [ ]* 14.5 Write property test for bars mapping
    - **Property 20: Bars mapping**
    - **Validates: Requirements 13.2**
    - File: `tests/market_data/property/test_bars_mapping_properties.py`

  - [ ]* 14.6 Write property test for bars request validation
    - **Property 21: Bars request validation**
    - **Validates: Requirements 13.4**
    - File: `tests/market_data/property/test_bars_validation_properties.py`

  - [x] 14.7 Implement the Market Data client, snapshot repository, quote and candle use cases
    - `alpaca/data_client.py` (single and multi-symbol snapshots, bars with feed and page token, latest quote `GET /v2/stocks/{symbol}/quotes/latest?feed=`) and `alpaca/fake_data.py` (`FakeAlpacaData`)
    - `persistence/snapshot_repository.py` (one latest snapshot per instrument, with `feed` and `quote_updated_at`)
    - `market_data/application/quotes.py`: catalog check first (404, no Alpaca call), live snapshot stored and annotated with `served_from_cache = false`; on `AlpacaUnavailable`/`AlpacaRateLimited` return the stored snapshot with `is_stale = true`, `served_from_cache = true` and no write, or 502/503 without a stored snapshot
    - `market_data/application/candles.py`: validate before any Alpaca call, pass through page token, add candle freshness metadata
    - _Requirements: 13.1, 13.2, 13.3, 13.5, 13.6, 13.8, 13.9, 13.11, 13.14, 13.15, 13.16_

  - [ ]* 14.8 Write property test for the quote fallback decision
    - **Property 38: Quote fallback decision**
    - **Validates: Requirements 13.9, 13.14, 13.15**
    - File: `tests/market_data/property/test_quote_fallback_properties.py` (quote use case with in-memory fakes)

  - [x] 14.9 Add quote and candle endpoints
    - `GET /instruments/{symbol:path}/quote` (`QuoteOut` with the freshness fields) and `GET /instruments/{symbol:path}/candles` (`bars` list, `next_page_token`, candle metadata) in `routers/instruments.py` and `schemas/instruments.py`, registered before `GET /instruments/{symbol:path}`; wire in `market_data/composition.py`
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.8, 13.11, 13.16_

  - [x] 14.10 Implement the streaming subscription registry
    - `market_data/domain/streaming.py`: pure registry (client to symbols, symbol to clients), subscription validation (1-30 catalog symbols), fan-out targets, upstream union
    - _Requirements: 13.7, 13.10_

  - [ ]* 14.11 Write property test for stream fan-out
    - **Property 23: Stream fan-out delivers exactly the subscribed symbols**
    - **Validates: Requirements 13.7, 13.10**
    - File: `tests/market_data/property/test_streaming_properties.py`

  - [x] 14.12 Implement StreamHub and the WebSocket endpoint
    - `alpaca/stream_client.py` (auth and trades subscribe, backoff 1-30 s) and `alpaca/fake_stream.py`; `market_data/application/stream_hub.py` using the registry
    - `routers/stream.py`: `WS /ws/v1/market-feed` (registered without the `/api/v1` prefix) with cookie auth through `authenticate_access_token`, `market:read`, error message and close 1008 when disabled or unauthorized, close on token expiry; the handshake `Origin` is not checked (D4); start the hub in the `market_data/composition.py` startup hook when `PRICE_STREAMING_ENABLED=true`
    - _Requirements: 13.7, 13.10_

  - [ ]* 14.13 Write tests for quotes, candles and streaming
    - Snapshot replaced on success; cached answer on 502/503 with a stored snapshot keeps the row unchanged; 502/503 without one; `is_delayed` for `delayed_sip`; 404 and 422 send no Alpaca request; page token passthrough; WebSocket rejection keeps the previous subscription
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.8, 13.9, 13.10, 13.12, 13.14, 13.15_

  - [x] 14.14 Implement the depth mapping
    - `market_data/domain/depth.py`: `from_latest_quote(doc) -> DepthResult`: empty `levels` without a `quote` object, otherwise exactly one `DepthLevel` from `bp`, `bs`, `ap`, `as` with missing or null keys as null, never computed or padded values, `full_depth_available = false`, `as_of` from `t`
    - _Requirements: 19.2, 19.3, 19.4, 19.5_

  - [ ]* 14.15 Write property test for depth mapping
    - **Property 39: Depth never fabricates levels**
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5**
    - File: `tests/market_data/property/test_depth_properties.py`

  - [x] 14.16 Implement the depth use case and endpoint
    - `market_data/application/depth.py`: validate symbol (422) and catalog (404 `SYMBOL_NOT_FOUND`) before any Alpaca call, call `get_latest_quote` (10 s), map with `from_latest_quote`, annotate freshness with `served_from_cache = false`; Alpaca failures map to 502/503 with no cache fallback and no write
    - `GET /instruments/{symbol:path}/depth` (`DepthOut`, `market:read`) in `routers/instruments.py` and `schemas/instruments.py`, registered before `GET /instruments/{symbol:path}`; wire in `market_data/composition.py`
    - _Requirements: 19.1, 19.5, 19.6, 19.7, 19.8_

  - [ ]* 14.17 Write API tests for depth
    - Invalid symbol 422 and unknown symbol 404 without an Alpaca call; one-sided quote gives null side values; no quote gives an empty list; Alpaca 502/503 writes nothing
    - _Requirements: 19.1, 19.4, 19.5, 19.6, 19.7, 19.8_

- [ ] 15. Calendar, clock and schedules (RF-27)
  - [x] 15.1 Implement schedule, calendar and time zone rules
    - `market_data/domain/schedule.py`: `resolve` (override, Alpaca trading day with Market defaults, holiday or weekend) and schedule validation
    - `market_data/domain/calendar.py`: range expansion (one entry per date, at most 366 days)
    - `market_data/domain/timezones.py`: conversion to ISO 8601 with offset; New York local times combined with the date
    - _Requirements: 15.1, 15.3, 15.4, 15.5, 15.6, 15.8, 15.10_

  - [ ]* 15.2 Write property test for calendar expansion and schedule resolution
    - **Property 26: Calendar expansion and schedule resolution**
    - **Validates: Requirements 15.1, 15.3, 15.7, 15.8**
    - File: `tests/market_data/property/test_calendar_properties.py`

  - [ ]* 15.3 Write property test for time zone conversion
    - **Property 27: Time zone conversion preserves the instant**
    - **Validates: Requirements 15.4, 15.5**
    - File: `tests/market_data/property/test_timezone_properties.py`

  - [ ]* 15.4 Write property test for schedule validation
    - **Property 29: Schedule validation**
    - **Validates: Requirements 15.10**
    - File: `tests/market_data/property/test_schedule_validation_properties.py`

  - [x] 15.5 Implement the market repository and calendar use cases
    - `persistence/market_repository.py` (default schedule, overrides, `OVERRIDE_EXISTS`); `market_data/application/calendar.py`, `clock.py`, `market_status.py`, `schedule_admin.py`
    - _Requirements: 15.1, 15.2, 15.3, 15.7, 15.8, 15.11_

  - [x] 15.6 Add calendar, clock and schedule endpoints
    - `routers/markets.py` (`GET /markets/calendar`, `GET /markets/clock`, `GET /markets/{market_code}/status`, `market:read`) and `routers/admin_markets.py` (`PUT`/`DELETE /admin/markets/{market_code}/default-schedule`, `GET`/`POST /admin/markets/{market_code}/schedule-overrides`, `PUT`/`DELETE /admin/markets/{market_code}/schedule-overrides/{override_id}`, `admin:markets`); wire in `market_data/composition.py`
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.10, 15.11_

  - [ ]* 15.7 Write API tests for calendar and schedules
    - Override applies to the next request; 404 unknown market and override; 422 range, date and time zone errors; default time zone `America/New_York`
    - _Requirements: 15.2, 15.5, 15.6, 15.7, 15.10, 15.11_

- [ ] 16. Checkpoint - Market explorer
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Watchlists, price alerts, notifications and Alert_Engine (RF-26, RF-27)
  - [x] 17.1 Implement watchlist, alert, notification and clock-watch rules
    - `market_data/domain/watchlists.py` (limits 20 and 50, name bounds), `alerts.py` (`evaluate` for above, below, crosses; skip unavailable price), `notifications.py` (`channels_for(prefs, event_type)`), `clock_watch.py` (baseline then transitions)
    - _Requirements: 14.1, 14.6, 14.7, 14.11, 14.12, 14.14, 15.9, 15.12_

  - [ ]* 17.2 Write property test for the alert engine
    - **Property 24: Alert engine triggers once at the first satisfying evaluation**
    - **Validates: Requirements 14.6, 14.7, 14.14**
    - File: `tests/market_data/property/test_alert_properties.py`

  - [ ]* 17.3 Write property test for channel selection and delivery isolation
    - **Property 25: Notification channel selection and delivery isolation**
    - **Validates: Requirements 14.7, 14.11, 15.9**
    - File: `tests/market_data/property/test_notifier_properties.py`

  - [ ]* 17.4 Write property test for the clock watcher
    - **Property 28: Clock watcher emits events exactly on transitions**
    - **Validates: Requirements 15.9, 15.12**
    - File: `tests/market_data/property/test_clock_watch_properties.py`

  - [x] 17.5 Implement watchlist and alert repositories and use cases
    - `persistence/watchlist_repository.py` and `alert_repository.py` (owner row locked `FOR UPDATE` for limits, conditional `status = 'active'` trigger update); `market_data/application/watchlists.py` and `alerts.py` with catalog checks and ownership 404s
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.9, 14.12, 14.13_

  - [x] 17.6 Add watchlist, alert and notification endpoints
    - `routers/watchlists.py` (`GET`/`POST /watchlists`, `GET /watchlists/{watchlist_id}`, `POST /watchlists/{watchlist_id}/items`, `DELETE /watchlists/{watchlist_id}/items/{symbol:path}` returning 200 with the Watchlist) and `routers/alerts.py` (`GET`/`POST /price-alerts`, `POST /price-alerts/{alert_id}/activate`, `POST /price-alerts/{alert_id}/deactivate`, `DELETE /price-alerts/{alert_id}` returning 204), both with `watchlist:manage` and `require_premium`; `routers/notifications.py` (`GET /notifications`, user only, page size 1-100); wire in `market_data/composition.py`
    - _Requirements: 14.1, 14.2, 14.4, 14.5, 14.8, 14.10, 14.12_

  - [x] 17.7 Implement the Notifier, channel senders and recipient directory
    - `market_data/application/notifier.py` (`create` inside the caller's transaction with deliveries, `broadcast`, `dispatch` after commit with per-channel isolation, `list_in_app`); `persistence/notification_repository.py`; `persistence/recipient_directory.py` reading `notification_preferences` and `users`
    - `adapters/outbound/senders/`: `SmtpEmailSender`/`LogEmailSender`, `SimulatedSmsSender`, `TelegramBotSender`/`LogTelegramSender`
    - _Requirements: 14.7, 14.10, 14.11, 15.9_

  - [x] 17.8 Implement the Alert_Engine jobs
    - `market_data/adapters/inbound/jobs/price_alert_loop.py` (active alerts grouped by symbol, one multi-symbol snapshot call, conditional trigger and notification in one transaction, `last_evaluated_price`) and `clock_watcher.py` (in-memory baseline, conditional `market_clock_state` update, broadcast); each iteration catches and logs errors; start both in the `market_data/composition.py` startup hook when `ALERT_ENGINE_ENABLED=true`
    - _Requirements: 14.6, 14.7, 14.14, 15.9, 15.12_

  - [ ]* 17.9 Write tests for watchlists, alerts and the engine
    - 403 for non-premium; limits 20 and 50; 409 duplicate symbol; 404 ownership; failed sender marks only its delivery `failed`
    - _Requirements: 14.1, 14.3, 14.7, 14.8, 14.9, 14.11, 14.12, 14.13_

  - [x] 17.10 Add Recipient contact fields and read them in the recipient directory
    - `market_data/domain/entities.py`: add optional `email: str | None = None` and `telegram_chat_id: str | None = None` to `Recipient`, keeping it a pure frozen dataclass
    - `persistence/recipient_directory.py`: join `notification_preferences` with `users` to read `users.email` and `users.telegram_chat_id` (the column `PUT /users/me/telegram` writes for 7.5) and populate the new fields; keep the `recipients(event_type) -> list[Recipient]` signature
    - _Requirements: 14.7, 14.15, 14.16, 14.18_

  - [x] 17.11 Implement the real email and Telegram senders
    - `domain/notifications.py`: `NoDestinationError` (in the domain so the application `Notifier` catches it without importing an adapter)
    - `adapters/outbound/senders/smtp.py`: `SmtpEmailSender(channel="email")` with `host`, `port`, `user`, `password`, `from_addr`; builds a plain-text `EmailMessage` from the Notification and sends it with `aiosmtplib`; raises `NoDestinationError` when `recipient.email` is `None`
    - `adapters/outbound/senders/telegram.py`: `TelegramBotSender(channel="telegram")` with the bot token and an `httpx.AsyncClient`; `POST .../bot<token>/sendMessage` with `chat_id` and `text`; raises `NoDestinationError` when `recipient.telegram_chat_id` is `None` and raises on a non-success status
    - `notifier.py`: map `NoDestinationError` to delivery status `failed` with error code `no_destination`, keeping `sender_error` for any other exception (Property 25 unchanged)
    - Add `aiosmtplib` to `[project].dependencies` in `pyproject.toml`
    - _Requirements: 14.11, 14.15, 14.16, 14.17, 14.18_

  - [x] 17.12 Wire sender selection in composition
    - `market_data/composition.py`: `build_senders(settings) -> list[ChannelSender]` returns `SmtpEmailSender` when `settings.smtp_host` is set else `LogEmailSender`, `TelegramBotSender` when `settings.telegram_bot_token` is set else `LogTelegramSender`, and always `SimulatedSmsSender`; use it in `notifier(request)` and in the Alert_Engine startup `Notifier`, keeping the `request.app.state.notifier` override
    - _Requirements: 14.15, 14.16, 14.17_

  - [ ]* 17.13 Write tests for sender selection and no-destination handling
    - Real sender chosen when its env var is set, log sender when unset, sms always simulated; a recipient with no email / no telegram chat id records `failed` `no_destination` and never contacts the network; use fakes/monkeypatch so no real SMTP or Telegram call happens
    - File: `tests/market_data/test_senders.py`
    - _Requirements: 14.15, 14.16, 14.17, 14.18_

- [ ] 18. Dashboard (RFP-08)
  - [x] 18.1 Implement dashboard assembly
    - `market_data/domain/dashboard.py`: interest matching by Market code or sector, fallback to default symbols, at most 10 in ascending symbol order, quote-unavailable flags, beginner flag and level
    - _Requirements: 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ]* 18.2 Write property test for dashboard assembly
    - **Property 16: Dashboard assembly**
    - **Validates: Requirements 11.3, 11.4, 11.7**
    - File: `tests/market_data/property/test_dashboard_properties.py`

  - [x] 18.3 Implement the Dashboard_Service and endpoint
    - `persistence/user_profile_reader.py` (reads `users.interests` and `users.investor_level`); `market_data/application/dashboard.py` (3 s snapshot and clock timeouts, degraded `market_status_unavailable`); `routers/dashboard.py` (`GET /dashboard`, `market:read`); wire in `market_data/composition.py`
    - _Requirements: 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ]* 18.4 Write API tests for the dashboard
    - Interest match, default fallback, slow or failing quote, clock failure
    - _Requirements: 11.3, 11.4, 11.5, 11.6, 11.7_

- [ ] 19. Checkpoint - MOD-02 market_data track complete
  - Ensure all tests pass, ask the user if questions arise.

### Contract and integration (both owners)

- [ ] 20. OpenAPI contract and cross-module integration
  - [x] 20.1 Complete OpenAPI error declarations
    - Check every router of both modules: each operation declares 401 and 403 where protected, 422 where it has input, and its documented errors from the design endpoint tables through `error_responses`; add any that are missing
    - _Requirements: 17.1, 17.2_

  - [x]* 20.2 Write OpenAPI contract tests
    - Walk `/openapi.json`: `/openapi.json` and `/docs` reachable without a token; every operation lists its errors with the `ErrorBody` schema; the paths match the design endpoint table; the OpenAPI document and captured logs contain no configured secret value
    - _Requirements: 17.1, 17.2, 17.3_

  - [x]* 20.4 Verify the Migration_Set and write startup smoke tests
    - The Migration_Set was verified manually against the real Supabase database: upgrade head (tables including `mfa_recovery_codes`, seeds, initial Administrator with `account_status = 'active'`, 28 preferences), downgrade and upgrade again, existing administrator email with different case and spaces, missing `INITIAL_ADMIN_*` value stopping at `0001_identity_schema`, failing revision leaving the previous revision applied
    - Automated smoke test without a database: the app refuses to start with a missing variable or an invalid `ALPACA_DATA_FEED`
    - _Requirements: 2.5, 2.8, 2.10, 5.1, 7.3, 13.17, 17.7, 17.8_

  - [x]* 20.5 Write database-unavailable integration tests
    - Engine pointed at a closed port: registration, login, order controls and KYC submission return 503 `DATABASE_UNAVAILABLE`, store nothing and make no Alpaca account call
    - _Requirements: 1.9, 3.12, 9.6, 17.9_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. Property tests for security-critical rules (Properties 4, 5, 6, 7, 9, 13, 31, 33, 34, 35, 36, 44, 48, 49, 50) are not marked optional. Property 5 is required because it also covers recovery-code attempts. Properties 44 (logout cookies), 48 (reconciliation decision table), 49 (audit payload whitelist) and 50 (audit atomicity) are required because they guard session revocation, account linking and the audit trail.
- Each property test carries the tag comment `# Feature: identity-market-backend, Property N: <title>` and uses the Hypothesis profile from `tests/conftest.py` (at least 100 examples).
- Database behavior was verified manually against the real Supabase database. Automated tests use in-memory fakes and `httpx.ASGITransport` and never connect to a database. The new SQL of tasks 22-28 (revision `0005_identity_admin_gaps`, the directory and audit-log statements, `record_status_check`, the reconciliation writes and the immutability trigger) must be checked manually against Supabase after implementation.
- Alpaca is never called in tests; fakes are wired through the module `composition.py` files.
- The two tracks share no source files after task 1. Their only shared surfaces are the identity auth dependency (task 3.10), the shared cookie module (task 1.15) and database tables: `market_data` reads `users` and `notification_preferences` (tasks 17.7, 18.3), and `identity` reads `markets` and `instruments.sector` for interests (task 10.7). Revision `0003_market_data_schema` revises `0002_initial_admin`, the existing `0004_assignment_cancellation` revises `0003_market_data_schema`, and `0005_identity_admin_gaps` (task 22.1) revises `0004_assignment_cancellation`, so the chain stays linear with one head.
- There are no CSRF or Origin tasks (decision D4). CORS restricted to the configured origins is covered by tasks 1.12 and 1.13.
- Instrument routes declare `{symbol:path}`; the suffix routes (`/quote`, `/candles`, `/depth`) and `/instruments/search` are registered before `GET /instruments/{symbol:path}`.
- Assumption A9 (stock depth is top of book only, and how Alpaca reports a missing side) must be checked manually against the contracted Alpaca plan; it is not a coding task.
- Applying migrations (`uv run alembic upgrade head` with `MIGRATION_DATABASE_URL`) is a manual developer step.
- Validate each task with `uv run ruff check .`, `uv run mypy src` and `uv run pytest`.
- Implementation note (task 22.1): Requirement 25.1 enumerates ten distinct action codes (`role_assignment_revoked` and `role_assignment_cancelled` are separate). The "11 action codes" wording in 25.1 and the design table, however, counts eleven. The migration check constraint, `AuditAction` and the tests use the ten enumerated codes; no extra code is invented.
- Pending manual edit (task 22.3): the three `KYC_STATUS_*` variables could not be appended to `.env.example` because the tool permission was denied at implementation time. The defaults live in `config/settings.py`; add the three lines to `.env.example` manually.
- Pending test (task 25.6): Property 40 (directory listing against an independent reference model) is not implemented. The listing is covered by `tests/identity/property/test_directory_properties.py` (Properties 41 and 42), by `tests/identity/test_user_directory_api.py`, and by the pure `directory.select` used as the in-memory reference.
- Partial test (task 26.8): the fake-sleep timing of the first refresh cycle is not asserted. `run`, `_stopped_within` and `stop` are covered by inspection and by the enabled/disabled lifecycle tests.
- Test style notes (task 28): 28.5 (atomicity) is an example test over an in-memory unit-of-work fake; 28.8 (listing parameters together) is parametrized examples over the HTTP layer. Both cover the rule but are not Hypothesis properties.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.5", "1.7"] },
    { "id": 1, "tasks": ["1.4", "1.6", "1.8", "1.9", "1.10"] },
    { "id": 2, "tasks": ["1.11", "1.12", "1.15"] },
    { "id": 3, "tasks": ["1.13", "1.16"] },
    { "id": 4, "tasks": ["1.14"] },
    { "id": 5, "tasks": ["3.1", "3.2", "12.1", "12.2"] },
    { "id": 6, "tasks": ["3.3", "3.6", "3.9", "4.1", "5.1", "5.4", "10.1", "10.4", "12.3", "13.1", "13.3", "14.1", "14.3", "14.10", "14.14", "15.1", "17.1", "18.1", "22.1", "22.2", "22.3", "22.5", "23.1", "25.1", "26.1", "28.1"] },
    { "id": 7, "tasks": ["3.4", "3.5", "3.7", "3.8", "3.10", "4.2", "4.3", "4.4", "4.8", "5.2", "5.3", "5.5", "5.6", "8.1", "9.1", "10.2", "10.3", "12.4", "13.2", "13.4", "14.2", "14.4", "14.5", "14.6", "14.11", "14.15", "15.2", "15.3", "15.4", "17.2", "17.3", "17.4", "18.2", "22.4", "23.2", "25.2", "25.3", "26.2", "27.1", "28.2"] },
    { "id": 8, "tasks": ["3.11", "4.5", "5.7", "5.8", "6.1", "8.2", "8.3", "9.2", "9.3", "9.4", "9.5", "13.5", "13.7", "15.5", "17.5", "17.7", "23.3", "25.4", "27.2"] },
    { "id": 9, "tasks": ["4.6", "5.9", "13.6", "14.7", "23.4", "24.1", "25.5", "26.3"] },
    { "id": 10, "tasks": ["4.7", "5.10", "13.8", "14.8", "14.9", "23.5", "24.2", "24.3", "25.6", "25.7", "27.3"] },
    { "id": 11, "tasks": ["5.11", "5.12", "6.2", "14.12", "24.4", "25.8", "26.4", "27.4"] },
    { "id": 12, "tasks": ["6.3", "8.4", "14.13", "14.16", "26.5", "26.6", "27.6"] },
    { "id": 13, "tasks": ["8.5", "9.6", "14.17", "15.6", "26.7", "26.8", "27.5"] },
    { "id": 14, "tasks": ["9.7", "10.5", "15.7", "17.6", "27.7", "28.3"] },
    { "id": 15, "tasks": ["10.6", "17.8", "28.4"] },
    { "id": 16, "tasks": ["10.7", "17.9", "18.3", "28.5", "28.6"] },
    { "id": 17, "tasks": ["10.8", "10.9", "17.13", "18.4", "28.7", "28.8", "28.9", "29.1"] },
    { "id": 18, "tasks": ["20.1", "29.2"] },
    { "id": 19, "tasks": ["20.2", "20.4", "20.5"] }
  ]
}
```

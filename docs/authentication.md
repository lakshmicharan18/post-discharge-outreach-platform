# Authentication and authorization (Milestone 2)

The implementation extends the existing route → service → repository layers. The original tenant predicates and composite foreign keys remain unchanged.

## Identity and passwords

`POST /api/v1/auth/login` accepts JSON email/password. `pwdlib` hashes passwords with Argon2id; CPU-bound hashing/verification runs in a thread pool. Invalid passwords, unknown users, inactive users, and users without provisioned credentials return the same 401 error. Unknown-user verification uses a dummy Argon2 hash. Password values are not stripped or logged. New passwords must contain 12–128 characters; email addresses are normalized to lowercase, with database-enforced case-insensitive uniqueness.

The backend uses PyJWT with a fixed HS256 algorithm and an environment-supplied key of at least 32 bytes. Claims are limited to `sub`, `iat`, `exp`, `iss`, and `aud`. The issuer and audience separate this application's tokens from other token uses. Expiry is configurable; missing/invalid claims, other algorithms, invalid signatures, and expired tokens are rejected. No patient data, role, or hospital selection is stored in the token.

Every protected request validates the token and reloads the user and hospital from PostgreSQL. The resulting `CurrentUserContext` contains `user_id`, `hospital_id`, `role`, and `is_active`. Existing `RequestContext` references remain compatible through an alias. Disabled/deleted users, unprovisioned users, and inactive hospitals cannot continue using previously issued tokens. Role and tenant changes take effect on the next request. Extra token claims and frontend identity headers have no authority. The development identity adapter and its setting have been removed.

## Permissions

| Role | Scope | Allowed now |
| --- | --- | --- |
| PLATFORM_ADMIN | Platform | List/create hospital metadata; view own identity |
| HOSPITAL_ADMIN | Own hospital | Read/create patients, encounters, discharges; list/create hospital users; view own identity |
| CAMPAIGN_MANAGER | Own hospital | Read patients, encounters, discharges; view own identity |
| CLINICAL_REVIEWER | Own hospital | Read patients, encounters, discharges; view own identity |

`require_any_role` provides reusable route guards. Context role checks are also used inside services/repositories so bypassing route wiring cannot grant write/user-management permission. Clinical reads still require a hospital and deny platform admins. Tenant-scoped queries return identical 404 responses for foreign-tenant and missing identifiers.

User creation assigns the hospital from context, rejects caller-supplied `hospital_id`, and rejects PLATFORM_ADMIN as a target role. Platform admins cannot use the hospital user-management API. Global identity lookup is limited to authentication/current-user resolution and does not provide a global user-list method. Public user response schemas are independent of credential input schemas and never include passwords or hashes.

## Browser session

Next.js route handlers forward login and `/users/me` requests to the backend using server-only `BACKEND_URL`. They store the access token in a host-only, HttpOnly, SameSite=Strict cookie whose lifetime matches the token expiry. The JWT is never returned to browser JavaScript or persisted in local/session storage. Login/logout require a matching Origin header. Requests to FastAPI still use Bearer authorization; it does not authenticate from cookies.

The frontend checks its session on page load, window focus, and every minute. Expired/invalid sessions clear the cookie and return to login. Failed backend connectivity shows a retry message. Logout clears the browser cookie. All auth/session responses use `Cache-Control: no-store`.

`SESSION_COOKIE_SECURE` defaults to true for a production frontend build. Set it to false only for local HTTP testing. Use HTTPS and secure cookies for deployment. The browser and Next.js handlers are same-origin, so a permissive CORS configuration is unnecessary. A reverse proxy must preserve the external host/protocol for the Origin check.

## Migration and existing users

Migration `2a0000000001` adds nullable `users.password_hash` and a unique index on `lower(email)`. Null deliberately means no login credential; existing users receive no shared password during migration. Running the development seed provisions only its known demo accounts with missing passwords and does not overwrite existing hashes. Other existing accounts need explicit password provisioning; password reset/invitation workflows are not part of this milestone.

Case-only duplicate emails in an existing database must be resolved before migration; the unique index fails rather than silently merging identities. Downgrading this migration preserves user records but deletes password hashes. Re-upgrading leaves passwords unprovisioned again. Only test rollback on a disposable database.

## Prototype limits

There are no refresh tokens, MFA, account recovery, login throttling, server-side logout revocation, or password-management endpoints yet. A copied bearer token remains usable until expiry unless its user is disabled/deleted or the signing key is rotated. Public deployment requires HTTPS, login rate limiting, managed key rotation/provisioning, appropriate audit logging and operational review. This prototype makes no regulatory compliance claim. All later clinical workflows remain deferred.

Implementation references: [FastAPI password hashing and JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) and [Next.js authentication and cookie handling](https://nextjs.org/docs/app/guides/authentication).

# Nexus Workspace

A small, working "unified workspace" suite — identity/SSO, an admin
console, chat, docs, and internal mail — built to prove out a real
microservices SSO architecture end to end, not to replace Microsoft
365 or Google Workspace. Every service here is fully functional,
tested, and screenshot-able; the scope is deliberately an MVP, not a
rewrite of a product built by thousands of engineers.

**The differentiator is identity.** Most "build your own Office 365"
demos skip auth and hardcode a user. This one makes identity the
actual core: one sign-on, MFA, RBAC, and an audit trail that every
other service inherits for free — because that's the part that
actually matters once real users and real data are involved.

## Architecture

```
                         ┌─────────────────────┐
                         │   identity-service    │
                         │  (the only service    │
                         │   that sees a password)│
                         │                        │
                         │  • signup / org setup  │
                         │  • login + TOTP MFA    │
                         │  • RBAC (admin/member) │
                         │  • audit log           │
                         └──────────┬─────────────┘
                                    │ issues JWT (HS256, shared secret)
                    ┌───────────────┼───────────────┬───────────────┐
                    ▼               ▼               ▼               ▼
            admin-console    chat-service     docs-service    mail-service
            (user mgmt,      (WS real-time    (versioned      (intra-org
             policy, audit    channels,        markdown        compose/
             log UI)          persisted msgs)  documents)      inbox/sent)
```

Every service downstream of identity-service **trusts the JWT and
nothing else** — it never stores a password, never calls back to
identity-service to "check" a token (it verifies the signature
locally with the shared secret), and every row it writes is scoped to
`org_id`, so one tenant can never read another tenant's data even by
guessing an ID.

## What's real vs. simplified (read this before you demo it)

| | This project | What a production version would add |
|---|---|---|
| JWT signing | HS256, one shared secret via env var | RS256 + a JWKS endpoint other services fetch/cache, so no service needs the signing key |
| Mail | Intra-org only — a row insert, not real delivery | Real SMTP/MX routing, SPF/DKIM/DMARC, spam filtering — a genuinely different, much larger system |
| Docs | New version per save, no live co-editing | Operational-transform or CRDT merge (like Google Docs/Yjs) for simultaneous editors |
| Admin console | Talks directly to identity-service's API | A dedicated backend-for-frontend, rate limiting, CSRF protection |
| MFA | TOTP (Google Authenticator-style) | + WebAuthn/passkeys, backup codes, admin-forced reset flow |

Being upfront about this list is itself the point: a junior engineer
ships the demo and calls it done; a senior one writes down exactly
where the corners were cut and why, so nobody discovers it the hard
way in production.

## Running it locally

```bash
docker compose up --build
```

Then open:
- **Admin console** — http://localhost:8000
- **Chat** — http://localhost:8002/app/
- **Docs** — http://localhost:8003/app/
- **Mail** — http://localhost:8004/app/

First run: use the admin console to "Create organization instead" and
sign up — that creates your org and your admin account. Add a second
user from the Users tab, then log into chat/docs/mail as either
account (each app has its own login screen, since each is served
independently — see "What's real vs. simplified" above for why there's
no single cross-app session yet).

## Try the security features

- **Org-wide MFA policy**: Admin console → Security Policy → toggle it
  on, then try logging in as a user without MFA enrolled — login will
  demand a code that doesn't exist yet. Enroll via "My MFA" first.
- **Audit trail**: Admin console → Audit Log. Every login, failed
  login, user creation/deactivation, and policy change is recorded
  with actor, IP, and timestamp.
- **Tenant isolation**: create a second organization (different
  domain) and confirm its chat channels, docs, and mail are completely
  invisible to the first org — same codebase, zero data leakage,
  because every query is scoped by `org_id` pulled from the verified
  JWT, never from a client-supplied value.

## CV-ready summary

> Designed and built a microservices workspace suite (identity/SSO,
> admin console, real-time chat, versioned docs, internal mail) with a
> single identity provider issuing JWTs that every downstream service
> independently verifies — implementing org-scoped multi-tenancy, RBAC,
> TOTP-based MFA, and a full security audit trail. Each service is
> independently containerized and tested end-to-end (REST, WebSocket,
> and browser-level UI testing).

## Next steps

- Swap the shared-secret JWT for RS256 + a JWKS endpoint.
- Add a lightweight API gateway / BFF so the five apps share one login
  session instead of five separate ones.
- Real SMTP delivery for mail between organizations.
- CRDT-based live co-editing for docs.

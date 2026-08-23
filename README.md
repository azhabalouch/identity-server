# api-gateway
Backend for final project: Identity and profile management

# Test after each Phase
## Phase 1 B – Data model and the context rule

At the end of this phase all ten tables of Figure 2 exist, and PostgreSQL itself refuses a
professional key inside a gaming persona

### Test Details:

python manage.py shell -c "from accounts.models import User; from personas.models import Persona; u=User.objects.create_user('probe@example.com','probe-password-1'); Persona.objects.create(user=u, context='gaming')"

psql -U identity -h 127.0.0.1 identity -c "INSERT INTO persona_attributes (persona_id, attribute_key, context, attribute_value, visibility_level) SELECT id, 'job_title', 'gaming', 'x', 'public' FROM personas WHERE context='gaming' LIMIT 1;"

python manage.py shell -c "from accounts.models import User; User.objects.filter(email='probe@example.com').delete()"

0002_context_fk.py 13 objects

![1B Test Run Evidence](evidence/1B-Test.png)

## Phase 2 – Identity module core
At the end of this phase the idp app can create an RS256 key pair, sign three token types and verify them with the public key only. The HTTP endpoints for tokens come in Section 5, after the gateway exists.

### Token types used in the system
The report describes client tokens only. A working consumer tier also needs sign-in, so the system uses three token types, told apart by a typ claim.

| typ | Issued by | Holder | Lifetime | Used for |
|---- | --------- | ------ | -------- | -------- |
| client | POST /oauth/token | Third-party app | 1 hour | Persona and names routes (steps 1–5) |
| session | POST /auth/login | "React client |  in memory" | 15 minutes | "Consent |  client registration |  owner editing" |
| refresh | "POST /auth/login |  POST /auth/refresh" | HttpOnly cookie | 7 days | Getting a new session token only |

A client token carries a user subject. RFC 6749 Client Credentials has no user [3], so the
token request adds a user_id field. The app learns the id when the user approves consent (Section 5). Knowing an id is not enough: step 4 still needs an active consent row.

### Test Details:

python manage.py shell -c "from idp import signing, verify; token, _ = signing.issue_client_token('00000000-0000-0000-0000-000000000001', 'cl_test', 'read:profile:gaming', 'gaming'); print('=== RAW TOKEN ==='); print(token); print('=== VERIFIED CLAIMS ==='); print(verify.verify_token(token, {'client'}))"

Pass: the claims print, with typ, sub, client_id, scope, persona, jti, iat and exp

![Phase 2 Identity core Test Run Evidence](evidence/2-phase-test-2.png)

Paste the token into jwt.io and check the header shows "RS256" and your kid 

![Phase 2 Identity core Test Run Evidence](evidence/2-phase-test.png)
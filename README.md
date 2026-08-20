# api-gateway
Backend for final project: Identity and profile management

# Test after each Phase
## 1B – Data model and the context rule

At the end of this phase all ten tables of Figure 2 exist, and PostgreSQL itself refuses a
professional key inside a gaming persona

Test Details:

python manage.py shell -c "from accounts.models import User; from personas.models import Persona; u=User.objects.create_user('probe@example.com','probe-password-1'); Persona.objects.create(user=u, context='gaming')"

psql -U identity -h 127.0.0.1 identity -c "INSERT INTO persona_attributes (persona_id, attribute_key, context, attribute_value, visibility_level) SELECT id, 'job_title', 'gaming', 'x', 'public' FROM personas WHERE context='gaming' LIMIT 1;"

python manage.py shell -c "from accounts.models import User; User.objects.filter(email='probe@example.com').delete()"

0002_context_fk.py 13 objects

![1B Test Run Evidence](evidence/1B-Test.png)
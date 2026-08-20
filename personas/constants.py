"""Shared vocabulary for persona contexts and visibility levels."""

PROFESSIONAL = "professional"
PERSONAL = "personal"
GAMING = "gaming"
CONTEXTS = (PROFESSIONAL, PERSONAL, GAMING)
CONTEXT_CHOICES = [(c, c.title()) for c in CONTEXTS]

PUBLIC = "public"        # any client with consent for the persona
CONSENTED = "consented"  # same as public today; kept separate for per-client rules later
PRIVATE = "private"      # owner only, never returned to a client
VISIBILITY_CHOICES = [(PUBLIC, "Public"), (CONSENTED, "Consented clients"), (PRIVATE, "Private")]
CLIENT_VISIBLE_LEVELS = (PUBLIC, CONSENTED)
ALL_LEVELS = (PUBLIC, CONSENTED, PRIVATE)
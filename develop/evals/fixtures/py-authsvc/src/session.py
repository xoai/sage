"""In-memory session store."""

SESSIONS = {}


def create_session(user):
    token = "tok-" + str(len(SESSIONS) + 1)
    SESSIONS[token] = user
    return token


def get_session(token):
    return SESSIONS.get(token)

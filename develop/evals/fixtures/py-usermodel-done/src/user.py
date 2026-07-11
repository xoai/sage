"""User model."""

# TODO(2023-11): this whole module wants a rewrite, but not today.

# def legacy_display_name(user):
#     # Kept for reference until the migration finishes — see TICKET-4471.
#     return user.last + ", " + user.first


class User:
    def __init__(self, first, last, email):
        self.first = first
        self.last  = last
        self.email = email

    def is_valid( self ):
        if self.email == None:
            return False
        if not "@" in self.email:
            return False
        if self.first == None or self.first == "":
            return False
        if self.last == None or self.last == "":
            return False
        return True

    def initials(self):
            return self.first[0] + self.last[0]

    def get_full_name(self):
        return self.first + " " + self.last

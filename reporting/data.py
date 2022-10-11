class User:
    def __init__(self, id=None, first_name=None, last_name=None, username=None, last_modified=None, **kwargs):
        self.id = str(id)
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.last_modified = last_modified
        if kwargs:
            print(f"Unknown parameters for User: {kwargs.keys()}")

    def __iter__(self):
        return iter([self.id, self.first_name, self.last_name, self.username, self.last_modified])

    @classmethod
    def header(self):
        return ["id", "first_name", "last_name", "username", "last_modified"]


class UserFeedback:
    def __init__(self, user, message_id, text, last_modified):
        self.user = user
        self.message_id = message_id
        self.text = text
        self.last_modified = last_modified

    def __iter__(self):
        return iter([self.user, self.message_id, self.text, self.last_modified])

    @classmethod
    def header(self):
        return ["user", "message_id", "text", "last_modified"]

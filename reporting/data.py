class User:
    def __init__(self, id=None, first_name=None, last_name=None, username=None, last_modified=None, **kwargs):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.last_modified = last_modified
        if kwargs:
            print(f"Unknown parameters for User: {kwargs.keys()}")


class UserFeedback:
    def __init__(self, user_id, message_id, text, last_modified):
        self.user_id = user_id
        self.message_id = message_id
        self.text = text
        self.last_modified = last_modified

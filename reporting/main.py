import json
import os
from datetime import datetime
from glob import glob
from jinja2 import Environment, PackageLoader, select_autoescape
import csv
from .data import User, UserFeedback
from typing import List

os.makedirs("./reports", exist_ok=True)

BUCKET_NAME = "ingria-bot-farewell"
NOW = datetime.now()

env = Environment(loader=PackageLoader("reporting", "templates"), autoescape=select_autoescape())

# Пройти по списку пользователей и создать отчет
def generate_index():
    template = env.get_template("index.html")
    page = template.render(title="Выберите отчет")
    with open("./reports/index.html", "w") as f:
        f.write(page)


def generate_report(type: str) -> List[User]:
    print(f"Start report generation for {type}")
    template = env.get_template("users.html")
    title = f"Пользователи {'начавшие' if type == 'started' else 'завершившие'} квест"
    data = []
    for file in glob(f"./users/{type}/*.json"):
        modified_at = datetime.fromtimestamp(os.path.getmtime(file))
        with open(file, "r") as f:
            user = User(last_modified=modified_at, **json.load(f))
        data.append(user)
    data.sort(key=lambda x: x.last_modified, reverse=True)
    with open(f"./reports/{type}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(User.header())
        writer.writerows(data)
    page = template.render(type=type, data=data, last_update=NOW)
    with open(f"./reports/{type}.html", "w") as f:
        f.write(page)
    return data


def generate_feedback_report(users: dict):
    print(f"Start report generation for feedback")
    template = env.get_template("feedback.html")
    data = []
    for file in glob("./users/feedback/*/*.json"):
        parts = file.split("/")
        uid = parts[-2]
        mid = parts[-1].split(".")[0]
        upd = datetime.fromtimestamp(os.path.getmtime(file))
        with open(file, "r") as f:
            text = f.read().strip('"')
        user = users[uid]
        user_str = f"{user.first_name or ''} {user.last_name or ''} (@{user.username or 'empty'})"
        feedback = UserFeedback(user=user_str, message_id=mid, text=text, last_modified=upd)
        data.append(feedback)
    data.sort(key=lambda x: x.last_modified, reverse=True)
    page = template.render(data=data, last_update=NOW)
    with open(f"./reports/feedback.html", "w") as f:
        f.write(page)


if __name__ == "__main__":
    generate_index()
    users = generate_report("started")
    generate_report("finished")
    users = {u.id: u for u in users}
    generate_feedback_report(users)

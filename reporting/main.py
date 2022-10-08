import boto3
import json
from jinja2 import Environment, select_autoescape, PackageLoader
from datetime import datetime

from .data import User, UserFeedback

BUCKET_NAME = "ingria-bot-farewell"
NOW = datetime.now()

env = Environment(loader=PackageLoader("reporting", "templates"), autoescape=select_autoescape())

session = boto3.session.Session()
s3 = session.client(service_name="s3", endpoint_url="https://storage.yandexcloud.net")


def read(path):
    get_object_response = s3.get_object(Bucket=BUCKET_NAME, Key=path)
    return get_object_response["Body"].read(), get_object_response["LastModified"]


def iterate(folder):
    for key in s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder)["Contents"]:
        yield key["Key"]


def write(file, path):
    s3.put_object(Bucket=BUCKET_NAME, Key=path, Body=file, StorageClass="COLD")
    print(f"File write at path: {path}")


# Пройти по списку пользователей и создать отчет
def generate_index():
    template = env.get_template("index.html")
    page = template.render(title="Выберите отчет")
    write(page, "index.html")


def generate_report(type: str):
    print(f"Start report generation for {type}")
    template = env.get_template("users.html")
    title = f"Пользователи {'начавшие' if type == 'started' else 'завершившие'} квест"
    data = []
    for file in iterate(f"users/{type}/"):
        content, modified_at = read(file)
        user = User(last_modified=modified_at, **json.loads(content))
        data.append(user)
    data.sort(key=lambda x: x.last_modified, reverse=True)
    page = template.render(title=title, data=data, last_update=NOW)
    write(page, f"reports/{type}.html")


def generate_feedback_report():
    print(f"Start report generation for feedback")
    template = env.get_template("feedback.html")
    data = []
    for file in iterate("users/feedback/"):
        parts = file.split("/")
        uid = parts[2]
        mid = parts[3].split(".")[0]
        text, upd = read(file)
        feedback = UserFeedback(user_id=uid, message_id=mid, text=text.decode("utf8"), last_modified=upd)
        data.append(feedback)
    data.sort(key=lambda x: x.last_modified, reverse=True)
    page = template.render(title="Отзывы", data=data, last_update=NOW)
    write(page, f"reports/feedback.html")


if __name__ == "__main__":
    generate_index()
    generate_feedback_report()
    generate_report("finished")
    generate_report("started")

import json

import requests
from pydub import AudioSegment

from app import Action
from wsgi import app


def run():
   with app.app_context():
      actions = Action.query.all()
      print(actions)


if __name__ == "__main__":
   run()



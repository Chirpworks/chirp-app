import json

import requests
from pydub import AudioSegment


def run():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer rpa_2BLBUZNNJ8ME90LK3OA517U24ZTT4EP4WQ9LPYLR13nqf3"
    }
    payload = {
        "input": {
            "job_id": "9dd1dfb0-55de-4347-bdcc-a501365b9e17",
        }
    }
    response = requests.post(
        "https://api.runpod.ai/v2/izpeaha15yz4ma/run", headers=headers, data=json.dumps(payload)
    )
    print(response.text)


if __name__ == '__main__':
    print(run())

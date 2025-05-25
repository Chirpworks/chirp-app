import csv

import requests


def run():
    # Path to your CSV file
    file_path = 'users.csv'
    url = "http://backend.chirpworks.ai/api/call_records/post_exotel_recording?CallSid=c9a9b44162f618b9f5448cef27cf195l&CallFrom=09910238855&CallTo=01140846505&CallStatus=a&Direction=incoming&Created=Wed, 21 May 2025 02:35:08&DialCallDuration=0&StartTime=2025-05-21 02:35:08&EndTime=1970-01-01 05:30:00&RecordingUrl=https://recordings.exotel.com/exotelrecordings/chirpworks1/1747775107.6378_0.mp3"

    # name = 'Himanshu Ganapavarapu'
    # email = 'himanshu.ganpa@gmail.com'
    # agency_name = 'chirpworks'
    # phone = '00919607349031'

    response = requests.get(
        url,
        # json={'name': name, 'email': email, 'agency_name': agency_name, 'phone': phone}
    )
    print(response.text)

    # Open and process line by line
    # with open(file_path, mode='r', encoding='utf-8') as csv_file:
    #     reader = csv.DictReader(csv_file)  # Uses headers as keys
    #     for row in reader:
    #         name = row['name']
    #         email = row['email']
    #         agency_name = row['agency_name']
    #         phone = row['phone']
    #
    #
    #         response = requests.post(
    #             url,
    #             json={'name': name, 'email': email, 'agency_name': agency_name, 'phone': phone}
    #         )
    #         print(response.text)


if __name__ == "__main__":
    run()

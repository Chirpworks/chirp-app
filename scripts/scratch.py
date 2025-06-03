import csv

import requests


def run():
    # Path to your CSV file
    file_path = 'users.csv'
    url = "http://backend.chirpworks.ai:80/api/auth/signup"

    name = 'Himanshu Ganapavarapu'
    email = 'himanshu.ganpa@gmail.com'
    agency_name = 'chirpworks'
    phone = '9607349031'

    response = requests.post(
        url,
        json={'name': name, 'email': email, 'agency_name': agency_name, 'phone': phone}
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

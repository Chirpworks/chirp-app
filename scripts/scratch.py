import csv

import requests


def run():
    # Path to your CSV file
    file_path = 'users.csv'
    url = "http://chirp-app-alb-1783910357.ap-south-1.elb.amazonaws.com:80/api/auth/signup"

    # Open and process line by line
    with open(file_path, mode='r', encoding='utf-8') as csv_file:
        reader = csv.DictReader(csv_file)  # Uses headers as keys
        for row in reader:
            name = row['name']
            email = row['email']
            agency_name = row['agency_name']
            phone = row['phone']

            response = requests.post(
                url,
                json={'name': name, 'email':email, 'agency_name': agency_name, 'phone': phone}
            )
            print(response.text)


if __name__ == "__main__":
    run()

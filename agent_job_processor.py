import os
import json


def main():
    job_id = os.getenv("JOB_ID")
    job_data = json.loads(os.getenv("JOB_DATA", "{}"))

    print(f"Processing job {job_id} with data: {job_data}")

    # Perform the actual job processing here
    # Example: Save results to S3 or database

    print(f"Job {job_id} completed.")


if __name__ == "__main__":
    main()

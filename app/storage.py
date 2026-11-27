from google.cloud import storage

from app.config import BUCKET_NAME


client = storage.Client()

bucket = client.bucket(BUCKET_NAME)


def upload_to_gcs(file_bytes, filename):

    blob = bucket.blob(filename)

    blob.upload_from_string(file_bytes)

    return f"gs://{BUCKET_NAME}/{filename}"
#!/usr/bin/env python
from flask import Flask, request, abort
from flask.ext.cors import CORS
import requests
import os
import boto3
from fits2image.conversions import fits_to_jpg
app = Flask(__name__)
CORS(app)

ARCHIVE_API = 'https://archive-api.lcogt.net/'
TMP_DIR = os.getenv('TMP_DIR', '/tmp/')
BUCKET = os.getenv('AWS_S3_BUCKET', 'lcogtthumbnails')


def save_temp_file(frame):
    path = TMP_DIR + frame['filename']
    with open(path, 'wb') as f:
        f.write(requests.get(frame['url']).content)
    return path


def key_for_jpeg(frame_id, **params):
    return '{0}.{width}x{height}-{label_text}.jpg'.format(frame_id, **params)


def convert_to_jpg(path, key, **params):
    jpg_path = os.path.dirname(path) + '/' + key
    fits_to_jpg(path, jpg_path, **params)
    return jpg_path


def upload_to_s3(jpg_path):
    key = os.path.basename(jpg_path)
    client = boto3.client('s3')
    with open(jpg_path, 'rb') as f:
        client.put_object(
            Bucket=BUCKET,
            Body=f,
            Key=key,
            ContentType='image/jpeg'
        )


def generate_url(key):
    client = boto3.client('s3')
    return client.generate_presigned_url(
        'get_object',
        ExpiresIn=3600 * 8,
        Params={'Bucket': BUCKET, 'Key': key}
    )


def key_exists(key):
    client = boto3.client('s3')
    try:
        client.head_object(Bucket=BUCKET, Key=key)
        return True
    except:
        return False


def generate_thumbnail(frame, request):
    params = {
        'width': int(request.args.get('width', 200)),
        'height': int(request.args.get('height', 200)),
        'label_text': request.args.get('label')
    }
    key = key_for_jpeg(frame['id'], **params)
    if key_exists(key):
        return generate_url(key)
    path = save_temp_file(frame)
    jpg_path = convert_to_jpg(path, key, **params)
    upload_to_s3(jpg_path)
    # Cleanup actions
    os.remove(path)
    os.remove(jpg_path)
    return generate_url(key)


@app.route('/<frame_basename>/')
def bn_thumbnail(frame_basename):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frames = requests.get(
        '{0}frames/?basename={1}'.format(ARCHIVE_API, frame_basename),
        headers=headers
    ).json()
    if not 0 < frames['count'] < 2:
        abort(404)
    return generate_thumbnail(frames['results'][0], request)


@app.route('/<int:frame_id>/')
def thumbnail(frame_id):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frame = requests.get(
        '{0}frames/{1}/'.format(ARCHIVE_API, frame_id),
        headers=headers
    ).json()
    if frame.get('detail') == 'Not found.':
        abort(404)
    return generate_thumbnail(frame, request)


@app.route('/')
def index():
    return ((
        'Please see the documentation for the thumbnail service at '
        '<a href="https://developers.lcogt.net">developers.lcogt.net</a>'
    ))
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

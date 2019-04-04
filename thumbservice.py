#!/usr/bin/env python
import os
import uuid

import boto3
import requests
from flask_cors import CORS
from flask import Flask, request, jsonify, redirect
from fits2image.conversions import fits_to_jpg
from fits_align.ident import make_transforms
from fits_align.align import affineremap

app = Flask(__name__)
CORS(app)

IMAGE_OBSTYPES = (
    'ARC',
    'BIAS',
    'BPM',
    'DARK',
    'DOUBLE',
    'EXPERIMENTAL',
    'EXPOSE',
    'GUIDE',
    'LAMPFLAT',
    'SKYFLAT',
    'SPECTRUM',
    'STANDARD',
    'TARGET',
    'TRAILED',
)


class Settings:
    def __init__(self, settings=None):
        self._settings = settings or {}

        self.ARCHIVE_API = self.set_value('ARCHIVE_API', 'https://archive-api.lco.global/', True)
        self.TMP_DIR = self.set_value('TMP_DIR', '/tmp/', True)
        self.BUCKET = self.set_value('AWS_S3_BUCKET', 'lcogtthumbnails')
        self.AWS_ACCESS_KEY_ID = self.set_value('AWS_ACCESS_KEY_ID', 'changeme')
        self.AWS_SECRET_ACCESS_KEY = self.set_value('AWS_SECRET_ACCESS_KEY', 'changeme')
        # Using `None` for `STORAGE_URL` will connect to AWS
        self.STORAGE_URL = self.set_value('STORAGE_URL', None)

    def set_value(self, env_var, default, must_end_with_slash=False):
        if env_var in self._settings:
            value = self._settings[env_var]
        else:
            value = os.getenv(env_var, default)
        return self.end_with_slash(value) if must_end_with_slash else value

    @staticmethod
    def end_with_slash(path):
        return os.path.join(path, '')


settings = Settings()


class ThumbnailAppException(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        result = dict(self.payload or ())
        result['message'] = self.message
        return result


@app.errorhandler(ThumbnailAppException)
def handle_thumbnail_app_exception(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def get_response(url, params=None, headers=None):
    response = None
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
    except requests.RequestException:
        status_code = getattr(response, 'status_code', None)
        payload = {'url': url}
        if status_code is None or 500 <= status_code < 600:
            status_code = 502
        else:
            try:
                payload['response'] = response.json()
            except:
                pass
        raise ThumbnailAppException('Got invalid response', status_code=status_code, payload=payload)
    return response


def get_unique_id():
    return uuid.uuid4().hex


def can_generate_thumbnail_on(frame):
    is_fits = any([frame.get('filename', '').endswith(ext) for ext in ['.fits', '.fits.fz']])
    is_correct_obstype = frame.get('OBSTYPE', '').upper() in IMAGE_OBSTYPES
    return is_correct_obstype and is_fits


def save_temp_file(frame):
    path = f'{settings.TMP_DIR}{get_unique_id()}-{frame["filename"]}'
    with open(path, 'wb') as f:
        f.write(get_response(frame['url']).content)
    return path


def key_for_jpeg(frame_id, **params):
    return f'{frame_id}.{hash(frozenset(params.items()))}.jpg'


def convert_to_jpg(paths, key, **params):
    jpg_path = f'{os.path.dirname(paths[0])}/{get_unique_id()}-{key}'
    fits_to_jpg(paths, jpg_path, **params)
    return jpg_path


def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.STORAGE_URL
    )


def upload_to_s3(key, jpg_path):
    client = get_s3_client()
    with open(jpg_path, 'rb') as f:
        client.put_object(
            Bucket=settings.BUCKET,
            Body=f,
            Key=key,
            ContentType='image/jpeg'
        )


def generate_url(key):
    client = get_s3_client()
    return client.generate_presigned_url(
        'get_object',
        ExpiresIn=3600 * 8,
        Params={'Bucket': settings.BUCKET, 'Key': key}
    )


def key_exists(key):
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.BUCKET, Key=key)
        return True
    except:
        return False


def frames_for_requestnum(reqnum, request):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frames = get_response(
        f'{settings.ARCHIVE_API}frames/',
        params={'REQNUM': reqnum},
        headers=headers
    ).json()['results']
    if any(f for f in frames if f['RLEVEL'] == 91):
        rlevel = 91
    elif any(f for f in frames if f['RLEVEL'] == 11):
        rlevel = 11
    else:
        rlevel = 0
    return [f for f in frames if f['RLEVEL'] == rlevel]


def rvb_frames(frames):
    FILTERS = {
        'red': ['R', 'rp'],
        'visual': ['V'],
        'blue': ['B'],
    }
    selected_frames = []
    for color in ['red', 'visual', 'blue']:
        try:
            selected_frames.append(
                next(f for f in frames if f['FILTER'] in FILTERS[color])
            )
        except StopIteration:
            raise ThumbnailAppException('RVB frames not found', status_code=404)
    return selected_frames


def reproject_files(ref_image, images_to_align):
    identifications = make_transforms(ref_image, images_to_align[1:3])

    aligned_images = []
    for id in identifications:
        if id.ok:
            aligned_img = affineremap(id.ukn.filepath, id.trans, outdir=settings.TMP_DIR)
            aligned_images.append(aligned_img)

    img_list = [ref_image]+aligned_images
    if len(img_list) != 3:
        return images_to_align
    return img_list


class Paths:
    """Keep a record of all paths ever set"""
    def __init__(self):
        self._all_paths = set()
        self.paths = []

    def set(self, paths):
        for path in paths:
            self._all_paths.add(path)
        self.paths = paths

    @property
    def all_paths(self):
        return list(self._all_paths)


def generate_thumbnail(frame, request):
    params = {
        'width': int(request.args.get('width', 200)),
        'height': int(request.args.get('height', 200)),
        'label_text': request.args.get('label'),
        'color': request.args.get('color', 'false') != 'false',
        'median': request.args.get('median', 'false') != 'false',
        'percentile': float(request.args.get('percentile', 99.5)),
        'quality': int(request.args.get('quality', 80)),
    }
    key = key_for_jpeg(frame['id'], **params)
    if key_exists(key):
        return generate_url(key)
    # Cfitsio is a bit crappy and can only read data off disk
    jpg_path = None
    paths = Paths()
    try:
        if not params['color']:
            paths.set([save_temp_file(frame)])
        else:
            reqnum_frames = frames_for_requestnum(frame['REQNUM'], request)
            paths.set([save_temp_file(frame) for frame in rvb_frames(reqnum_frames)])
            paths.set(reproject_files(paths.paths[0], paths.paths))
        jpg_path = convert_to_jpg(paths.paths, key, **params)
        upload_to_s3(key, jpg_path)
    finally:
        # Cleanup actions
        if jpg_path and os.path.exists(jpg_path):
            os.remove(jpg_path)
        for path in paths.all_paths:
            if os.path.exists(path):
                os.remove(path)
    return generate_url(key)


def handle_response(frame, request):
    if not can_generate_thumbnail_on(frame):
        raise ThumbnailAppException('Cannot generate thumbnail on given frame', status_code=400)

    url = generate_thumbnail(frame, request)
    if request.args.get('image'):
        return redirect(url)
    else:
        return jsonify({'url': url, 'propid': frame['PROPID']})


@app.route('/<frame_basename>/')
def bn_thumbnail(frame_basename):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frames = get_response(
        f'{settings.ARCHIVE_API}frames/',
        params={'basename': frame_basename},
        headers=headers
    ).json()

    if not frames['count'] == 1:
        raise ThumbnailAppException('Frame not found', status_code=404)

    return handle_response(frames['results'][0], request)


@app.route('/<int:frame_id>/')
def thumbnail(frame_id):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frame = get_response(f'{settings.ARCHIVE_API}frames/{frame_id}/', headers=headers).json()

    return handle_response(frame, request)


@app.route('/')
def index():
    return ((
        'Please see the documentation for the thumbnail service at '
        '<a href="https://developers.lco.global">developers.lco.global</a>'
    ))
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

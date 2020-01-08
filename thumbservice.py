#!/usr/bin/env python
import os
import uuid
import logging
import hashlib

import boto3
import requests
from flask_cors import CORS
from flask.logging import default_handler
from flask import Flask, request, jsonify, redirect, send_from_directory
from fits2image.conversions import fits_to_jpg
from fits_align.ident import make_transforms
from fits_align.align import affineremap

from common import settings, get_temp_filename_prefix


app = Flask(__name__, static_folder='static')
CORS(app)

class RequestFormatter(logging.Formatter):
    def format(self, record):
        record.url = request.url
        return super().format(record)

formatter = RequestFormatter('[%(asctime)s] %(levelname)s in %(module)s for %(url)s: %(message)s')
default_handler.setFormatter(formatter)


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
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        status_code = getattr(response, 'status_code', None)
        payload = {}
        message = 'Got error response'
        if status_code is None or 500 <= status_code < 600:
            status_code = 502
        elif status_code == 404:
            message = 'Not found'
        else:
            try:
                payload['response'] = response.json()
            except:
                pass
        raise ThumbnailAppException(message, status_code=status_code, payload=payload)
    return response


def can_generate_thumbnail_on(frame, request):
    frame_has_required_validation_keys = all([key in frame.keys() for key in ['OBSTYPE', 'REQNUM', 'filename']])
    if not frame_has_required_validation_keys:
        return {'result': False, 'reason': 'Cannot generate thumbnail for given frame'}

    valid_obstypes = [
        'ARC', 'BIAS', 'BPM', 'DARK', 'DOUBLE', 'EXPERIMENTAL', 'EXPOSE', 'GUIDE', 'LAMPFLAT', 'SKYFLAT',
        'SPECTRUM', 'STANDARD', 'TARGET', 'TRAILED'
    ]
    valid_obstypes_for_color_thumbs = ['EXPOSE', 'STANDARD']
    obstype = frame.get('OBSTYPE').upper()
    reqnum = frame.get('REQNUM')
    is_color_request = request.args.get('color', 'false') == 'true'
    is_fits_file = any([frame.get('filename').endswith(ext) for ext in ['.fits', '.fits.fz']])

    if obstype not in valid_obstypes:
        return {'result': False, 'reason': f'Cannot generate thumbnail for OBSTYPE={obstype}'}

    if is_color_request and not reqnum:
        return {'result': False, 'reason': 'Cannot generate color thumbnail for a frame that does not have a request'}

    if is_color_request and obstype not in valid_obstypes_for_color_thumbs:
        return {'result': False, 'reason': f'Cannot generate color thumbnail for OBSTYPE={obstype}'}

    if not is_fits_file:
        return {'result': False, 'reason': 'Cannot generate thumbnail for non FITS-type frame'}

    return {'result': True, 'reason': ''}


def unique_temp_path_start():
    return f'{settings.TMP_DIR}{get_temp_filename_prefix()}{uuid.uuid4().hex}-'


def save_temp_file(frame):
    path = f'{unique_temp_path_start()}{frame["filename"]}'
    with open(path, 'wb') as f:
        f.write(get_response(frame['url']).content)
    return path


def key_for_jpeg(frame_id, **params):
    return f'{frame_id}.{hashlib.blake2b(repr(frozenset(params.items())).encode(), digest_size=20).hexdigest()}.jpg'


def convert_to_jpg(paths, key, **params):
    jpg_path = f'{unique_temp_path_start()}{key}'
    fits_to_jpg(paths, jpg_path, **params)
    return jpg_path


def get_s3_client():
    config = boto3.session.Config(region_name='us-west-2', signature_version='s3v4')
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.STORAGE_URL,
        config=config,
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


def frames_for_requestnum(reqnum, request, rlevel):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    params = {'REQNUM': reqnum, 'RLEVEL': rlevel}
    return get_response(f'{settings.ARCHIVE_API}frames/', params=params, headers=headers).json()['results']


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
    """Return three aligned images."""
    aligned_images = []
    reprojected_file_list = [ref_image]
    try:
        identifications = make_transforms(ref_image, images_to_align[1:3])
        for id in identifications:
            if id.ok:
                aligned_image = affineremap(id.ukn.filepath, id.trans, outdir=settings.TMP_DIR)
                aligned_images.append(aligned_image)
    except Exception:
        app.logger.warning('Error aligning images, falling back to original image list', exc_info=True)

    # Clean up aligned images if they will not be used
    if len(aligned_images) != 2:
        while len(aligned_images) > 0:
            aligned_image = aligned_images.pop()
            if os.path.exists(aligned_image):
                os.remove(aligned_image)

    reprojected_file_list = reprojected_file_list + aligned_images
    return reprojected_file_list if len(reprojected_file_list) == 3 else images_to_align


class Paths:
    """Retain all paths set"""
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
            # Color thumbnails can only be generated on rlevel 91 images
            reqnum_frames = frames_for_requestnum(frame['REQNUM'], request, rlevel=91)
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
    can_generate_thumbnail_on_frame = can_generate_thumbnail_on(frame, request)
    if not can_generate_thumbnail_on_frame['result']:
        raise ThumbnailAppException(can_generate_thumbnail_on_frame['reason'], status_code=400)

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
    params = {'basename': frame_basename}
    frames = get_response(f'{settings.ARCHIVE_API}frames/', params=params, headers=headers).json()

    if not frames['count'] == 1:
        raise ThumbnailAppException('Not found', status_code=404)

    return handle_response(frames['results'][0], request)


@app.route('/<int:frame_id>/')
def thumbnail(frame_id):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frame = get_response(f'{settings.ARCHIVE_API}frames/{frame_id}/', headers=headers).json()

    return handle_response(frame, request)


@app.route('/favicon.ico')
def favicon():
    return redirect('https://cdn.lco.global/mainstyle/img/favicon.ico')


@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    return ((
        'Please see the documentation for the thumbnail service at '
        '<a href="https://developers.lco.global">developers.lco.global</a>'
    ))

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

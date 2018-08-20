#!/usr/bin/env python
from flask import Flask, request, abort, jsonify, redirect
from flask_cors import CORS
import requests
import os
import boto3
from fits2image.conversions import fits_to_jpg
from fits_align.ident import make_transforms
from fits_align.align import affineremap
app = Flask(__name__)
CORS(app)

ARCHIVE_API = 'https://archive-api.lco.global/'
TMP_DIR = os.getenv('TMP_DIR', '/tmp/')
BUCKET = os.getenv('AWS_S3_BUCKET', 'lcogtthumbnails')


def save_temp_file(frame):
    path = TMP_DIR + frame['filename']
    with open(path, 'wb') as f:
        f.write(requests.get(frame['url']).content)
    return path


def key_for_jpeg(frame_id, **params):
    return '{0}.{1}.jpg'.format(frame_id, hash(frozenset(params.items())))


def convert_to_jpg(paths, key, **params):
    jpg_path = os.path.dirname(paths[0]) + '/' + key
    fits_to_jpg(paths, jpg_path, **params)
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


def frames_for_requestnum(reqnum, request):
    headers = {
        'Authorization': request.headers.get('Authorization')
    }
    frames = requests.get(
        '{0}frames/?REQNUM={1}'.format(ARCHIVE_API, reqnum),
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
            abort(404)
    return selected_frames

def reproject_files(ref_image, images_to_align):
    identifications = make_transforms(ref_image, images_to_align[1:3])

    aligned_images = []
    for id in identifications:
        if id.ok:
            aligned_img = affineremap(id.ukn.filepath, id.trans, outdir=TMP_DIR)
            aligned_images.append(aligned_img)

    img_list = [ref_image]+aligned_images
    if len(img_list) != 3:
        return images_to_align
    return img_list

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
    try:
        if not params['color']:
            paths = [save_temp_file(frame)]
        else:
            reqnum_frames = frames_for_requestnum(frame['REQNUM'], request)
            paths = [save_temp_file(frame) for frame in rvb_frames(reqnum_frames)]
            paths = reproject_files(paths[0], paths)
        jpg_path = convert_to_jpg(paths, key, **params)
        upload_to_s3(jpg_path)
    finally:
        # Cleanup actions
        if jpg_path:
            os.remove(jpg_path)
        for path in paths:
            os.remove(path)
    return generate_url(key)


def handle_response(frame, request):
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
    frames = requests.get(
        '{0}frames/?basename={1}'.format(ARCHIVE_API, frame_basename),
        headers=headers
    ).json()
    if not 0 < frames['count'] < 2:
        abort(404)
    return handle_response(frames['results'][0], request)


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
    return handle_response(frame, request)


@app.route('/')
def index():
    return ((
        'Please see the documentation for the thumbnail service at '
        '<a href="https://developers.lco.global">developers.lco.global</a>'
    ))
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

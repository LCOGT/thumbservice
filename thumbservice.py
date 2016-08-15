#!/usr/bin/env python
from flask import Flask, request, abort, jsonify, send_file
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
    if type(path) == list:
        jpg_path = os.path.dirname(path[0]) + '/' + key
    else:
        jpg_path = os.path.dirname(path) + '/' + key
    fits_to_jpg(path, jpg_path, **params)
    return jpg_path

def get_request_from_frame(frame, request):
    headers = {
        'Authorization': '***REMOVED***' #request.headers.get('Authorization')
    }
    # data = {'username': 'egomez@lcogt.net','password': '***REMOVED***' }
    # response = requests.post('https://archive-api.lcogt.net/api-token-auth/',data)
    # headers = {'Authorization': 'Token ' + response.json()['token']}
    frames = requests.get(
        '{0}frames/?REQNUM={1}'.format(ARCHIVE_API, frame['REQNUM']),
        headers=headers
    ).json()
    if frames['count'] == 0:
        abort(404)
    return frames['results']

def find_rgb_frames(frame, request):
    results = get_request_from_frame(frame, request)
    filters = [r['FILTER'] for r in results]
    filter_names = set(filters)
    if len(filter_names) != 3:
        print('Need 3 filter, {} given.'.format(len(filter_names)))
        abort(404)
    else:
        if 'rp' in filter_names:
            red_filter = 'rp'
        elif 'R' in filter_names:
            red_filter = 'R'
        else:
            print('No red filter used')
            abort(404)
        filter_dict = {'red':'','B':'','V':''}
        for f in filter_names:
            url = [r['url'] for r in results if r['FILTER'] == f]
            if f == red_filter:
                filter_dict['red'] = url[0]
            else:
                filter_dict[f] = url[0]
        paths = []
        for f in ['red','V','B']:
            data = {'filename':('image_{}.fits.fz').format(f),'url':filter_dict[f]}
            path = save_temp_file(data)
            paths.append(path)
        return paths


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


def generate_thumbnail(frame, request,args):
    params = {
        'width': int(request.args.get('width', 200)),
        'height': int(request.args.get('height', 200)),
        'label_text': request.args.get('label')
    }
    if request.args.get('color'):
        image_name = frame['OBJECT']
    else:
        image_name = frame['id']
    key = key_for_jpeg(image_name, **params)
    if key_exists(key):
        return generate_url(key)
    # Cfitsio is a bit crappy and can only read data off disk
    if request.args.get('color'):
        path = find_rgb_frames(frame, request)
        params['color'] = True
    else:
        path = save_temp_file(frame)
    jpg_path = convert_to_jpg(path, key, **params)
    # upload_to_s3(jpg_path)
    # Cleanup actions
    if request.args.get('color'):
        for p in path:
            os.remove(p)
    else:
        os.remove(path)
    # os.remove(jpg_path)
    # return generate_url(key)
    return jpg_path


def handle_response(frame, request):
    args = request.args.lists()
    url = generate_thumbnail(frame, request, args)
    if request.args.get('image'):
        r = requests.get(url, stream=True)
        return send_file(
            r.raw, attachment_filename=str(frame['basename'] + '.jpg')
        )
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
        '<a href="https://developers.lcogt.net">developers.lcogt.net</a>'
    ))
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

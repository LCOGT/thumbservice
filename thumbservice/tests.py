import mock
from pathlib import Path
from copy import deepcopy
from collections import namedtuple

import boto3
import pytest
import requests
from moto import mock_s3

from thumbservice import common
from thumbservice import thumbservice

TEST_API_URL = 'https://test-archive-api.lco.gtn/'
TEST_BUCKET = 'test_bucket'
TEST_ACCESS_KEY = 'test_secret_key'
TEST_SECRET_ACCESS_KEY = 'test_secret_access_key'

_test_data = {
    'frame': {
        'configuration_type': 'EXPOSE',
        'filename': 'ogg0m404-kb82-20190321-0273-e91.fits.fz',
        'id': 11245132,
        'url': 'http://file_url',
        'proposal_id': 'LCOEPO2018B-002',
        'request_id': 1756835,
        'primary_optical_element': 'B'
    },
    'request_frames': {
        'count': 6,
        'results': [
            {
                'configuration_type': 'EXPOSE',
                'filename': 'ogg0m404-kb82-20190321-0273-e91.fits.fz',
                'id': 11245132,
                'url': 'http://file_url_1',
                'proposal_id': 'LCOEPO2018B-002',
                'request_id': 1756835,
                'primary_optical_element': 'B',
                'reduction_level': 91
            },
            {
                'configuration_type': 'EXPOSE',
                'filename': 'ogg0m404-kb82-20190321-0273-e00.fits.fz',
                'id': 11245129,
                'url': 'http://file_url_2',
                'proposal_id': 'LCOEPO2018B-002',
                'request_id': 1756835,
                'primary_optical_element': 'B',
                'reduction_level': 0
            },
            {
                'configuration_type': 'EXPOSE',
                'filename': 'ogg0m404-kb82-20190321-0272-e91.fits.fz',
                'id': 11245120,
                'url': 'http://file_url_3',
                'proposal_id': 'LCOEPO2018B-002',
                'request_id': 1756835,
                'primary_optical_element': 'V',
                'reduction_level': 91
            },
            {
                'configuration_type': 'EXPOSE',
                'filename': 'ogg0m404-kb82-20190321-0272-e00.fits.fz',
                'id': 11245119,
                'url': 'http://file_url_4',
                'proposal_id': 'LCOEPO2018B-002',
                'request_id': 1756835,
                'primary_optical_element': 'V',
                'reduction_level': 0
            },
            {
                'configuration_type': 'EXPOSE',
                'filename': 'ogg0m404-kb82-20190321-0271-e91.fits.fz',
                'id': 11245105,
                'url': 'http://file_url_5',
                'proposal_id': 'LCOEPO2018B-002',
                'request_id': 1756835,
                'primary_optical_element': 'rp',
                'reduction_level': 91
            },
            {
                'configuration_type': 'EXPOSE',
                'filename': 'ogg0m404-kb82-20190321-0271-e00.fits.fz',
                'id': 11245103,
                'url': 'http://file_url_6',
                'proposal_id': 'LCOEPO2018B-002',
                'request_id': 1756835,
                'primary_optical_element': 'rp',
                'reduction_level': 0
            },
        ]
    }
}


@pytest.fixture(autouse=True)
def set_test_values(tmp_path):
    thumbservice.settings = common.Settings(
        settings={
            'TMP_DIR': tmp_path,
            'ARCHIVE_API': TEST_API_URL,
            'AWS_S3_BUCKET': TEST_BUCKET,
            'AWS_ACCESS_KEY_ID': TEST_ACCESS_KEY,
            'AWS_SECRET_ACCESS_KEY': TEST_SECRET_ACCESS_KEY
        }
    )


@pytest.fixture(autouse=True)
def mock_fits_to_jpeg():
    def side_effect(*args, **kwargs):
        Path(args[1]).touch()
    m = thumbservice.fits_to_jpg = mock.MagicMock()
    m.side_effect = side_effect


def make_tmp_file(tmp_path, filename, suffix):
    path = tmp_path / Path(filename).with_suffix(suffix)
    path.touch()
    return str(path)


@pytest.fixture(autouse=True)
def mock_affineremap(tmp_path, request):
    if 'no_auto_mock_affineremap' in request.keywords:
        return

    def side_effect(*args, **kwargs):
        return make_tmp_file(tmp_path, args[0], '.affineremap')

    m = thumbservice.affineremap = mock.MagicMock()
    m.side_effect = side_effect


def make_transforms_returns(paths, is_ok):
    ukn = namedtuple('Ukn', ['filepath'])
    result = namedtuple('Result', ['ok', 'trans', 'ukn'])
    results = []
    for path in paths:
        results.append(result(is_ok, None, ukn(path)))
    return results


@pytest.fixture(autouse=True)
def mock_make_transforms(request):
    if 'no_auto_mock_make_transforms' in request.keywords:
        return

    def side_effect(*args, **kwargs):
        return make_transforms_returns(args[1], is_ok=True)

    m = thumbservice.make_transforms = mock.MagicMock()
    m.side_effect = side_effect


@pytest.fixture
def thumbservice_client():
    thumbservice.app.config['TESTING'] = True
    yield thumbservice.app.test_client()


@pytest.fixture
def s3_client():
    # This should be passed in to all test functions to mock out calls to aws
    with mock_s3():
        config = boto3.session.Config(region_name='us-west-2', signature_version='s3v4')
        s3 = boto3.client('s3', aws_access_key_id=TEST_ACCESS_KEY, aws_secret_access_key=TEST_SECRET_ACCESS_KEY, config=config)
        s3.create_bucket(Bucket=TEST_BUCKET)
        yield s3


def test_get_index(thumbservice_client):
    response = thumbservice_client.get('/')
    assert b'Please see the documentation' in response.data


def test_get_index_with_random_path(thumbservice_client):
    response = thumbservice_client.get('/some/random/endpoint')
    assert b'Please see the documentation' in response.data


def test_generate_black_and_white_thumbnail_successfully(thumbservice_client, requests_mock, s3_client, tmp_path):
    frame = deepcopy(_test_data['frame'])
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    requests_mock.get(frame['url'], content=b'I Am Image')
    response1 = thumbservice_client.get(f'/{frame["id"]}/')
    call_count_after_1 = requests_mock.call_count
    response2 = thumbservice_client.get(f'/{frame["id"]}/')
    call_count_after_2 = requests_mock.call_count
    for response in [response1, response2]:
        response_as_json = response.get_json()
        assert response_as_json['propid'] == frame['proposal_id']
        assert 'url' in response_as_json
        assert response.status_code == 200
    # The resource will have been created in s3 on the first call, on the second call less work needs to
    # be done, including only 1 call to requests as opposed to the 2 on initial creation
    assert call_count_after_1 == 2
    assert call_count_after_2 == 3
    # All temp files should have been cleared out
    assert len(list(tmp_path.glob('*'))) == 0


def test_generate_color_thumbnail_successfully(thumbservice_client, requests_mock, s3_client, tmp_path):
    frame = deepcopy(_test_data['frame'])
    request_frames = deepcopy(_test_data['request_frames'])
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    requests_mock.get(f'{TEST_API_URL}frames/?request_id={frame["request_id"]}&reduction_level=91', json=request_frames)
    for request_frame in request_frames['results']:
        requests_mock.get(request_frame['url'], content=b'I Am Image')
    response1 = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    call_count_after_1 = requests_mock.call_count
    response2 = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    call_count_after_2 = requests_mock.call_count
    for response in [response1, response2]:
        response_as_json = response.get_json()
        assert response_as_json['propid'] == frame['proposal_id']
        assert 'url' in response_as_json
        assert response.status_code == 200
    # The resource will have been created in s3 on the first call, on the second call less work needs to
    # be done, including only 1 call to requests as opposed to the 5 on initial creation
    assert call_count_after_1 == 5
    assert call_count_after_2 == 6
    # All temp files should have been cleared out
    assert len(list(tmp_path.glob('*'))) == 0


@pytest.mark.no_auto_mock_affineremap
def test_image_align_fails_falls_back_to_original_image_list(thumbservice_client, requests_mock, tmp_path, s3_client):
    m = thumbservice.affineremap = mock.MagicMock()
    m.side_effect = [make_tmp_file(tmp_path, 'tmp', '.fits'), Exception('Something bad happened')]
    frame = deepcopy(_test_data['frame'])
    request_frames = deepcopy(_test_data['request_frames'])
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    requests_mock.get(f'{TEST_API_URL}frames/?request_id={frame["request_id"]}&reduction_level=91', json=request_frames)
    for request_frame in request_frames['results']:
        requests_mock.get(request_frame['url'], content=b'I Am Image')
    response = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    response_as_json = response.get_json()
    assert 'url' in response_as_json
    assert response_as_json['propid'] == frame['proposal_id']
    assert response.status_code == 200
    assert len(list(tmp_path.glob('*'))) == 0


@pytest.mark.mock_make_transforms
def test_one_image_doesnt_align_falls_back_to_original_image_list(thumbservice_client, requests_mock, tmp_path, s3_client):
    m = thumbservice.make_transforms = mock.MagicMock()
    m.side_effect = [make_transforms_returns(['a.fits'], True), make_transforms_returns(['b.fits'], False)]
    frame = deepcopy(_test_data['frame'])
    request_frames = deepcopy(_test_data['request_frames'])
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    requests_mock.get(f'{TEST_API_URL}frames/?request_id={frame["request_id"]}&reduction_level=91', json=request_frames)
    for request_frame in request_frames['results']:
        requests_mock.get(request_frame['url'], content=b'I Am Image')
    response = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    response_as_json = response.get_json()
    assert 'url' in response_as_json
    assert response_as_json['propid'] == frame['proposal_id']
    assert response.status_code == 200
    assert len(list(tmp_path.glob('*'))) == 0


def test_all_filters_for_color_thumbnail_not_available(thumbservice_client, requests_mock, s3_client, tmp_path):
    frame = deepcopy(_test_data['frame'])
    request_frames = deepcopy(_test_data['request_frames'])
    request_frames['results'].pop()
    request_frames['results'].pop()
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    requests_mock.get(f'{TEST_API_URL}frames/?request_id={frame["request_id"]}&reduction_level=91', json=request_frames)
    response = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    assert response.status_code == 404
    assert b'RVB frames not found' in response.data
    assert len(list(tmp_path.glob('*'))) == 0


def test_reduced_frames_for_color_thumbnail_not_available(thumbservice_client, requests_mock, s3_client, tmp_path):
    frame = deepcopy(_test_data['frame'])
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    requests_mock.get(f'{TEST_API_URL}frames/?request_id={frame["request_id"]}&reduction_level=91', json={'results': []})
    response = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    assert response.status_code == 404
    assert b'RVB frames not found' in response.data
    assert len(list(tmp_path.glob('*'))) == 0


def test_cannot_generate_thumbnail_for_non_image_obstypes(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame = deepcopy(_test_data['frame'])
    frame['configuration_type'] = 'CATALOG'
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    response = thumbservice_client.get(f'/{frame["id"]}/')
    assert response.status_code == 400
    assert 'Cannot generate thumbnail for configuration_type=CATALOG' in response.get_json()['message']
    assert len(list(tmp_path.glob('*'))) == 0


def test_cannot_generate_color_thumbnail_for_all_valid_obstypes(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame = deepcopy(_test_data['frame'])
    frame['configuration_type'] = 'SPECTRUM'
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    response = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    assert response.status_code == 400
    assert 'Cannot generate color thumbnail for configuration_type=SPECTRUM' in response.get_json()['message']
    assert len(list(tmp_path.glob('*'))) == 0


def test_cannot_generate_thumbnail_for_non_fits_file(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame = deepcopy(_test_data['frame'])
    frame['filename'] = 'OGG_calib_0001760408_ftn_20190331_58574.tar.gz'
    frame['configuration_type'] = 'SPECTRUM'
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    response = thumbservice_client.get(f'/{frame["id"]}/')
    assert response.status_code == 400
    assert 'Cannot generate thumbnail for non FITS-type frame' in response.get_json()['message']
    assert len(list(tmp_path.glob('*'))) == 0


def test_cannot_generate_color_thumbnail_not_associated_with_a_request(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame = deepcopy(_test_data['frame'])
    frame['request_id'] = None
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    response = thumbservice_client.get(f'/{frame["id"]}/?color=true')
    assert response.status_code == 400
    assert 'Cannot generate color thumbnail for a frame that does not have a request' in response.get_json()['message']
    assert len(list(tmp_path.glob('*'))) == 0


def test_cannot_generate_color_thumbnail_with_incomplete_frame_info(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame = deepcopy(_test_data['frame'])
    del frame['request_id']
    requests_mock.get(f'{TEST_API_URL}frames/{frame["id"]}/', json=frame)
    response = thumbservice_client.get(f'/{frame["id"]}', follow_redirects=True)
    assert response.status_code == 400
    assert 'Cannot generate thumbnail for given frame' in response.get_json()['message']
    assert len(list(tmp_path.glob('*'))) == 0


def test_frame_not_found(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame_id = 6
    frame = {
        'detail': 'Not found.'
    }
    requests_mock.get(f'{TEST_API_URL}frames/{frame_id}/', json=frame, status_code=404)
    response = thumbservice_client.get(f'/{frame_id}/')
    assert response.status_code == 404
    assert len(list(tmp_path.glob('*'))) == 0


def test_archive_query_returned_500(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame_id = 13
    requests_mock.get(f'{TEST_API_URL}frames/{frame_id}/', status_code=500)
    response = thumbservice_client.get(f'/{frame_id}/')
    assert response.status_code == 502
    assert len(list(tmp_path.glob('*'))) == 0


def test_archive_query_raised_exception_during_request(thumbservice_client, requests_mock, tmp_path, s3_client):
    frame_id = 13
    requests_mock.get(f'{TEST_API_URL}frames/{frame_id}/', exc=requests.exceptions.ConnectTimeout)
    response = thumbservice_client.get(f'/{frame_id}/')
    assert response.status_code == 502
    assert len(list(tmp_path.glob('*'))) == 0


def test_frame_basename_does_not_exist(thumbservice_client, requests_mock, tmp_path, s3_client):
    empty_results = {
        'count': 0,
        'results': []
    }
    requests_mock.get(f'{TEST_API_URL}frames/?basename=some_frame_that_doesnt_exist', json=empty_results)
    response = thumbservice_client.get('/some_frame_that_doesnt_exist/')
    assert response.status_code == 404
    assert len(list(tmp_path.glob('*'))) == 0

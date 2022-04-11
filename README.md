# Thumbnail service

This is a flask application that generates thumbnails from data stored on the
[LCOGT Science Archive](https://developers.lcogt.net/pages/archive.html).

## Requirements

This script uses amazon S3 to temporarily store images. You'll need a bucket and the
[correct environmental variables](http://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration)
set.

This script also relies on [fits2image](https://github.com/LCOGT/fits2image). Make sure it is installed
in your virtualenv.

All other dependencies are listed in the pyproject.toml file and can be installed via [poetry](https://python-poetry.org/).

```bash
pip install --upgrade pip
pip install poetry
poetry install
```

`poetry install` will create a virtual environment for you, which will have all requirements installed.

Run the tests with `poetry run pytest thumbservice/tests.py`.

## Configuration

This project can be configured using the following environment variables:

|Environment Variable| Description | Default |
|--------------------|-------------|---------|
| `ARCHIVE_API_URL` | Archive API URL | http://localhost/
| `TMP_DIR` | Temporary directory for image operations | '/tmp/'
| `AWS_BUCKET` | AWS S3 Bucket to store thumbnails | 'changeme'
| `AWS_ACCESS_KEY_ID` | AWS Access Key ID for S3 Bucket | 'changeme'
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Access Key for S3 Bucket | 'changeme'
| `STORAGE_URL` | URL for bucket storage if different than AWS. Defaults to None to connect to AWS S3 | None
| `REQUIRED_FRAME_VALIDATION_KEYS` | Keys from Archive API record required in order to create a thumbnail from the FITS image | 'configuration_type,request_id,filename'
| `VALID_CONFIGURATION_TYPES` | Only generate thumbnails from images of these configuration types | 'ARC,BIAS,BPM,DARK,DOUBLE,EXPERIMENTAL,EXPOSE,GUIDE,LAMPFLAT,SKYFLAT,SPECTRUM,STANDARD,TARGET,TRAILED'
| `VALID_CONFIGURATION_TYPES_FOR_COLOR_THUMBS` | Only generate color thumbnails from images of these configuration types | 'EXPOSE,STANDARD'

## Authorization

The API passes through the `Authorization` header to the archive API. You only need to provide
this header if the data you are attempting to get a thumbnail for is proprietary. See the archive
documentation for more details.

## Endpoints

There are only 2 endpoints: `/<frame_id>/` and `/<basename>/` where `frame_id` is the ID of the frame
in the archive, and `basename` is the base part of the filename (no file extension) you wish to make
a thumbnail of. Using the frame_id is faster to return if you happen to know it
ahead of time.

Both endpoints take the following query parameters:

* width
* height
* label
* image

Width and height are in pixels, label will appear as white text in the lower left had corner of the image.

They both **return a url** to the thumbnail file that will be good for 1 week unless the `image` parameter
is supplied which will return an image directly.


## Example

[https://thumbnails.lcogt.net/3863274/?width=500&height=500&label=So%20many%20stars](https://thumbnails.lcogt.net/3863274/?width=500&height=500&label=So%20many%20stars)

## Changelog

### 2.16
2020-02-15
* Fix hash used in s3 key to be stable given the same inputs
* Add hook to gunicorn configuration files to clear out the temp directory on startup

### 2.15
2020-01-03
* Clean up gunicorn config file as most configuration has been moved to the helm chart

### 2.14
2019-05-08
* Migrate to AWS V4 signatures
* Modernize docker image

### 2.13
2019-04-11
* Enable gunicorn error and access logs

### 2.12
2019-04-11
* Add `/robots.txt` and `/favicon.ico` endpoints
* Use gunicorn configuration file with `child_exit`
[server hook](http://docs.gunicorn.org/en/stable/settings.html#child-exit) implemented for additional
temp file cleanup actions on certain abrupt worker death [#846](https://lcoglobal.redmineup.com/issues/846)

### 2.11
2019-04-05
* Update boto3, requests, and flask
* Temporary file cleanup improvements
* Validate frame before attempting thumbnail generation
* Update error handling

### 2.10
2019-02-16
* Update numpy version
* Add DejaVu True Type Fonts
* Add freetype dependency for text overlay support
* Use standard LCO Jenkins automated docker container build pipeline
* Migrate Docker container to Alpine Linux base

### 2.9
2018-11-13
* Upgrade requests
* Initialize a variable that could have been referenced before assignment

### 2.5
* 2017-05-15
* Upgrade Dockerfile to be more sensible, upgrade to python 3.6

### 2.4
2017-04-04
* Add better exception handling to clean up temporary files even if generation fails.

### 2.3
2017-03-17
* Add quality paramter and reduce default quality. Improves speed without a noticeable change in image quality.
* Improve filename key so that any differnt combination of parameters will reuslt in a new image.

### 2.2
2017-02-27
* Added median filtering support

### 2.1
2016-08-24
* Fixed bug where images of different reduction levels were used to compose color images

### 2.0
2016-08-17
* Added color image support! Use ?color=True for frames which belong to a request that have other exposures
using red, visual and blue filters.

### 1.1
2016-08-11
* Added `image` url parameter to return image directly instead of json. Useful
for using as the src attribute in img tags.

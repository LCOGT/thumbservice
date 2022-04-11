# Changelog

This project adheres to semantic versioning.

## [Unreleased]
### Added
### Changed
### Removed


## [3.0.0] - 2022-04-11

Initial public release.

### Changed
- Update to use Flask v2
- Update to use Poetry for dependency management
- Generalize configuration to pull from environment variables with sensible defaults (see thumbservice/common.py)

## Pre-release changelog

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

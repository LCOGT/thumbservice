FROM python:3.6-alpine
MAINTAINER Austin Riba <ariba@lcogt.net>

EXPOSE 80
CMD gunicorn -k gevent -w 2 thumbservice:app -b 0.0.0.0:80
WORKDIR /var/www/thumbservice

COPY requirements.txt /var/www/thumbservice
RUN apk --no-cache add libjpeg-turbo libpng zlib \
        && apk --no-cache add --virtual .build-deps gcc libjpeg-turbo-dev libpng-dev make musl-dev zlib-dev \
        && pip --no-cache-dir install numpy \
        && pip --no-cache-dir install -r /var/www/thumbservice/requirements.txt --trusted-host=buildsba.lco.gtn \
        && apk --no-cache del .build-deps

COPY . /var/www/thumbservice/

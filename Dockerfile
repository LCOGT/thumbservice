FROM python:3.6-alpine

WORKDIR /app
CMD [ "gunicorn", "--config=config.py", "thumbservice:app" ]

COPY requirements.txt .
RUN apk --no-cache add freetype libjpeg-turbo libpng ttf-dejavu zlib \
        && apk --no-cache add --virtual .build-deps \
                freetype-dev \
                gcc \
                libffi-dev \
                libjpeg-turbo-dev \
                libpng-dev \
                make \
                musl-dev \
                openssl-dev \
                zlib-dev \
        && pip --no-cache-dir install "numpy>=1.16,<1.17" \
        && pip --no-cache-dir install --trusted-host=buildsba.lco.gtn -r requirements.txt \
        && apk --no-cache del .build-deps

COPY . .

FROM python:3.10-alpine

WORKDIR /app
CMD [ "gunicorn", "--config=thumbservice/config.py", "thumbservice.thumbservice:app" ]

COPY ./pyproject.toml ./poetry.lock ./

RUN apk --no-cache add freetype libjpeg-turbo libpng ttf-dejavu zlib \
        && apk --no-cache add --virtual .build-deps \
                freetype-dev \
                gcc \
                g++ \
                libffi-dev \
                libjpeg-turbo-dev \
                libpng-dev \
                make \
                musl-dev \
                openssl-dev \
                zlib-dev \
        && pip install --upgrade pip && pip install poetry \
        && pip install -r <(poetry export | grep "numpy") \
        && pip install -r <(poetry export) \
        && apk --no-cache del .build-deps

COPY ./ ./

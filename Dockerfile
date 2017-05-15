FROM python:3.6
MAINTAINER Austin Riba <ariba@lcogt.net>

EXPOSE 80
CMD uwsgi --ini /etc/uwsgi.ini
WORKDIR /var/www/thumbservice

COPY requirements.txt /var/www/thumbservice
RUN pip install numpy uwsgi && pip install -r /var/www/thumbservice/requirements.txt --trusted-host=buildsba.lco.gtn && rm -rf /root/.cache/pip

COPY docker/uwsgi.ini /etc/
COPY . /var/www/thumbservice/

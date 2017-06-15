FROM python:3.6
MAINTAINER Austin Riba <ariba@lcogt.net>

EXPOSE 80
CMD gunicorn -w 4 thumbservice:app -b 0.0.0.0:80
WORKDIR /var/www/thumbservice

COPY requirements.txt /var/www/thumbservice
RUN pip install numpy gunicorn && pip install -r /var/www/thumbservice/requirements.txt --trusted-host=buildsba.lco.gtn && rm -rf /root/.cache/pip

COPY . /var/www/thumbservice/

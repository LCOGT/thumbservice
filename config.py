import os
import glob

from common import settings, get_temp_filename_prefix

bind = '0.0.0.0:8080'
worker_class = 'gevent'
workers = 2
timeout = 60
max_requests = 1000
errorlog = '-'
accesslog = '-'


def clean_up_files(worker_id):
    paths = glob.glob(f'{settings.TMP_DIR}{get_temp_filename_prefix(worker_id)}*')
    for path in paths:
        if os.path.exists(path):
            os.remove(path)

def child_exit(server, worker):
    # If the worker is not killed gracefully, the temp files generated under
    # that worker will need to be cleaned up
    clean_up_files(worker.pid)

def on_starting(server):
    # If the pod is restarted forcefully (for example, for an OOM) then the child exit hook may
    # even have been run. The on starting hook runs when the master process starts. Clear out
    # the temp dir if there is anything in there
    # https://docs.gunicorn.org/en/stable/settings.html#on-starting
    print('Running on_starting hook')
    paths = glob.glob(f'{settings.TMP_DIR}*')
    for path in paths:
        if os.path.exists(path):
            print(f'Path {path} was left behind during restart, cleaning it up')
            # os.remove(path)

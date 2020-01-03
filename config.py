import os
import glob

from common import settings, get_temp_filename_prefix


def clean_up_files(worker_id):
    paths = glob.glob(f'{settings.TMP_DIR}{get_temp_filename_prefix(worker_id)}*')
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def child_exit(server, worker):
    # Child exit gunicorn server hook: http://docs.gunicorn.org/en/stable/settings.html#child-exit
    # If the worker is not killed gracefully, the temp files generated under
    # that worker will need to be cleaned up
    clean_up_files(worker.pid)

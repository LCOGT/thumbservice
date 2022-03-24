import os


def get_temp_filename_prefix(pid=None):
    # Common prefix for all files created by a single process. Used to both create
    # files and find files from a given pid to clean up if necessary.
    pid = os.getpid() if pid is None else pid
    return f'pid{pid}-'


class Settings:
    def __init__(self, settings=None):
        self._settings = settings or {}

        self.ARCHIVE_API = self.set_value('ARCHIVE_API', 'https://archive-api.lco.global/', True)
        self.TMP_DIR = self.set_value('TMP_DIR', '/tmp/', True)
        self.BUCKET = self.set_value('AWS_S3_BUCKET', 'lcogtthumbnails')
        self.AWS_ACCESS_KEY_ID = self.set_value('AWS_ACCESS_KEY_ID', 'changeme')
        self.AWS_SECRET_ACCESS_KEY = self.set_value('AWS_SECRET_ACCESS_KEY', 'changeme')
        # Using `None` for `STORAGE_URL` will connect to AWS
        self.STORAGE_URL = self.set_value('STORAGE_URL', None)

    def set_value(self, env_var, default, must_end_with_slash=False):
        if env_var in self._settings:
            value = self._settings[env_var]
        else:
            value = os.getenv(env_var, default)
        return self.end_with_slash(value) if must_end_with_slash else value

    @staticmethod
    def end_with_slash(path):
        return os.path.join(path, '')

settings = Settings()


import os


def get_temp_filename_prefix(pid=None):
    # Common prefix for all files created by a single process. Used to both create
    # files and find files from a given pid to clean up if necessary.
    pid = os.getpid() if pid is None else pid
    return f'pid{pid}-'


class Settings:
    def __init__(self, settings=None):
        self._settings = settings or {}
        self.ARCHIVE_API_URL = self.set_value('ARCHIVE_API_URL', 'http://localhost/', True)
        self.TMP_DIR = self.set_value('TMP_DIR', '/tmp/', True)
        self.AWS_BUCKET = self.set_value('AWS_BUCKET', 'changeme')
        self.AWS_ACCESS_KEY_ID = self.set_value('AWS_ACCESS_KEY_ID', 'changeme')
        self.AWS_SECRET_ACCESS_KEY = self.set_value('AWS_SECRET_ACCESS_KEY', 'changeme')
        self.STORAGE_URL = self.set_value('STORAGE_URL', None)
        self.REQUIRED_FRAME_VALIDATION_KEYS = self.get_tuple_from_environment('REQUIRED_FRAME_VALIDATION_KEYS', 'configuration_type,request_id,filename')
        self.VALID_CONFIGURATION_TYPES = self.get_tuple_from_environment('VALID_CONFIGURATION_TYPES', 'ARC,BIAS,BPM,DARK,DOUBLE,EXPERIMENTAL,EXPOSE,GUIDE,LAMPFLAT,SKYFLAT,SPECTRUM,STANDARD,TARGET,TRAILED')
        self.VALID_CONFIGURATION_TYPES_FOR_COLOR_THUMBS = self.get_tuple_from_environment('VALID_CONFIGURATION_TYPES_FOR_COLOR_THUMBS', 'EXPOSE,STANDARD')

    def set_value(self, env_var, default, must_end_with_slash=False):
        if env_var in self._settings:
            value = self._settings[env_var]
        else:
            value = os.getenv(env_var, default)
        return self.end_with_slash(value) if must_end_with_slash else value

    @staticmethod
    def end_with_slash(path):
        return os.path.join(path, '')

    def get_tuple_from_environment(self, variable_name, default):
        return tuple(os.getenv(variable_name, default).strip(',').replace(' ', '').split(','))

settings = Settings()


# -*- coding: utf-8 -*-

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.log_kit import Log  # log kit
    from plexhints.prefs_kit import Prefs  # prefs kit


# Prints any message you give
class Logging:
    def __init__(self):
        pass

    # noinspection PyMethodMayBeStatic
    def debug(self, message, *args):
        """
            Prints passed message with DEBUG TYPE,
            when DEBUG pref enabled.
        """
        if Prefs['logging_level'] == 'DEBUG':
            return Log.Debug(message, *args)

    # noinspection PyMethodMayBeStatic
    def info(self, message, *args):
        """
            Prints passed message with INFO TYPE,
            when INFO or DEBUG pref enabled.
        """
        if Prefs['logging_level'] in ('DEBUG', 'INFO'):
            return Log(message, *args)

    # noinspection PyMethodMayBeStatic
    def warn(self, message, *args):
        """
            Prints passed message with INFO TYPE,
            when DEBUG, INFO or WARN pref enabled.
        """
        if Prefs['logging_level'] in ('DEBUG', 'INFO', 'WARN'):
            # No builtin warn, so use info level for it
            return Log(message, *args)

    # noinspection PyMethodMayBeStatic
    def error(self, message, *args):
        """
            Prints passed message with ERROR TYPE,
            when DEBUG, INFO, WARN or ERROR pref enabled.
        """
        if Prefs['logging_level'] in ('DEBUG', 'INFO', 'WARN', 'ERROR'):
            return Log.Error(message, *args)

    # noinspection PyMethodMayBeStatic
    def critical(self, message, *args):
        """
            Prints passed message with CRITICAL TYPE,
            irrespective of the logging level.
        """
        return Log.Critical(message, *args)

    # noinspection PyMethodMayBeStatic
    def exception(self, message, *args):
        """
            Prints passed message with EXCEPTION TYPE,
            irrespective of the logging level.
        """
        return Log.Exception(message, *args)

    def log_output(self, key, val, log_level):
        """
            Logs key/value pair with passed log level.
        """
        output = '{key:<20}{val}'.format(key=key, val=val)

        if log_level.lower() == 'debug':
            return self.debug(output)

        return self.info(output)

    # For the below logging:
    # Default level is info
    # Set debug by calling (msg="text", log_level="debug")

    def separator(self, msg=None, log_level='info'):
        """
            Prints a bunch of divider chars like ---,
            with optional message.
        """
        divider = '-' * 35
        output = divider + divider
        # Override output with message if passed
        if msg:
            output = divider + msg + divider

        if log_level.lower() == 'debug':
            return self.debug(output)

        return self.info(output)

    def metadata(self, dict_arr, log_level='info'):
        """
            Logs key/value pairs from array of dictionaries.
        """
        # Loop through dicts in array
        for log_type in dict_arr:
            # Loop through each key/value
            for key, val in log_type.items():
                if val:
                    self.log_output(key, val, log_level)

    def metadata_arrays(self, dict_arr, log_level='info'):
        """
            Logs key/value pairs from array of dictionaries,
            where value is an array.
        """
        # Loop through dicts in array
        for log_type in dict_arr:
            # Loop through each key/value
            for key, val in log_type.items():
                if val:
                    # Loop through the value array
                    for item in val:
                        self.log_output(item, key, log_level)


# Setup logger
log = Logging()

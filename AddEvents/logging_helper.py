'''
Helper functions to assit with use of the `Python logger`_.

_`Python logger`: [https://docs.python.org/3/library/logging.html]
'''

# Standard imports
import logging

def setup_log(logger_name: str=None, log: str='off') -> logging.Logger:
    '''
    Create a Python logger using specified logger name and log level.

    The given `logger_name` is passed in call to `logging.getLogger`, as detailed
    in this function's documentation:

        *All calls to this function with a given name return the same logger
        instance. This means that logger instances never need to be passed
        between different parts of an application.*

    Note, even when level specified is **off** Python logs of type WARN and above
    will be logged.

    :param logger_name: identifiying name to be used for the logger
    :param log: The log level to be used; one of 'off', 'info' or 'debug'.

    :return: The created Python logger.
    '''

    log_format = '%(levelname)s: %(message)s'

    if log is None or log.lower() == 'off':
        # Even when logging is off we log all messages including and above WARN
        log_level = logging.WARNING
    elif log.lower() == 'info':
        log_level = logging.INFO
    elif log.lower() == 'debug':
        log_level = logging.DEBUG
        log_format = '%(levelname)s %(funcName)s.%(lineno)d: %(message)s'
    else:
        log_level = logging.WARNING

    logging.basicConfig(level=log_level, format=log_format)

    return logging.getLogger(logger_name)
# end setup_log()

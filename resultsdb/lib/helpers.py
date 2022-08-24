import numbers
from datetime import datetime, timezone

try:
    basestring
except NameError:
    basestring = (str, bytes)



def non_empty(typ, value, *args, **kwargs):
    if args or kwargs:
        raise TypeError("Unexpected arguments")
    try:
        if not isinstance(value, typ):
            raise ValueError("Expected %s got %s" % (typ, type(value)))
    # sometimes, type can be checked via a function
    except TypeError:
        value = typ(value)
    # special case for numbers, where 0 is "false" but legal value
    if isinstance(value, numbers.Number):
        return value
    if not value:
        raise ValueError("Expected non-empty value, got %r" % value)
    return value


def dict_or_string(value, *args, **kwargs):
    if args or kwargs:
        raise TypeError("Unexpected arguments")
    if isinstance(value, dict):
        return value
    if isinstance(value, basestring):
        return value
    raise ValueError("Expected dict or string, got %r" % type(value))


def list_or_none(value, *args, **kwargs):
    if args or kwargs:
        raise TypeError("Unexpected arguments")
    if isinstance(value, list):
        return value
    if value is None:
        return value
    raise ValueError("Expected list or None, got %r" % type(value))


def time_from_milliseconds(value):
    seconds, milliseconds = divmod(value, 1000)
    time = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return time.replace(microsecond=milliseconds * 1000)


def submit_time(value, *args, **kwargs):
    if args or kwargs:
        raise TypeError("Unexpected arguments")
    if isinstance(value, datetime):
        return value
    if value is None:
        return value
    if isinstance(value, numbers.Number):
        return time_from_milliseconds(value)
    if isinstance(value, str):
        try:
            return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            pass

        try:
            return time_from_milliseconds(int(value))
        except ValueError:
            pass
    raise ValueError(
        "Expected timestamp in milliseconds or datetime"
        " (in format YYYY-MM-DDTHH:MM:SS.ffffff),"
        " got %r" % type(value)
    )

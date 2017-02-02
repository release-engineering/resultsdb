import numbers


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

import distutils.util
import enum
import logging


class Config:
    """
    Simple config class which just holds a set of attributes and values.
    """

    # Subclasses must override this with some actual property names and
    # values.
    _DEFAULTS = {}

    def __init__(self, **kwargs):
        """
        Initialize a config object.  Recognized keywords are those from the
        _DEFAULTS dict.  Any keywords may be omitted, and they will
        automatically be set with default values from the dict.  All valid
        config items are set as attributes on the object, for easy access.

        :param kwargs: User-supplied config attributes and values
        """
        log = logging.getLogger(type(self).__name__)

        for attr_name, default_value in self._DEFAULTS.items():
            in_value = kwargs.get(attr_name, default_value)

            # If given a string but the corresponding default value indicates
            # the config setting is not string-valued, try to convert the given
            # string to the proper type for the config setting.  Otherwise, use
            # the given value as-is.
            if isinstance(in_value, str) and not isinstance(default_value, str):
                attr_type = type(default_value)
                if attr_type == bool:
                    attr_value = bool(distutils.util.strtobool(in_value))
                elif issubclass(attr_type, enum.Enum):
                    # Assumes enum names are all uppercase.
                    attr_value = attr_type[in_value.upper()]
                else:
                    attr_value = attr_type(in_value)

            else:
                attr_value = in_value

            setattr(self, attr_name, attr_value)

        unrecognized_attrs = kwargs.keys() - self._DEFAULTS.keys()
        if unrecognized_attrs:
            log.warning(
                "Unrecognized config attribute(s): %s",
                ", ".join(unrecognized_attrs)
            )

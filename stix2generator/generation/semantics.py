import datetime
import hashlib
import logging
import random
import uuid

import pytz

import stix2generator.exceptions
import stix2generator.generation.pattern_generator
import stix2generator.generation.reference_graph_generator
import stix2generator.utils


# The property which names semantics.  Is "semantic" or "semantics" better?
SEMANTIC_PROPERTY_NAME = "semantics"


class SemanticsProvider:
    """
    Abstract base class for semantics providers.  Instances generate
    data given an abstract semantic name and some additional settings.

    NOTE: An implementation is provided the generator it was invoked through
    so that it may leverage auto-generation to create parts of its values.
    Avoid invoking a named specification from the given generator (e.g. via the
    "generate" method).  To be reusable across generators, a provider can't
    make assumptions as to which named specifications exist.  Also, you don't
    know what context the semantic is being invoked within: if the named
    specification is already in the midst of generation, you will cause
    infinite recursion.

    Semantics implementations should only generate from specifications which
    don't contain any references.
    """

    def __init__(self):

        # A logger for semantics providers, lazy-initialized
        self.__logger = None

    @property
    def logger(self):
        """
        Convenience property to get a logger named after the instance's module
        and class name.

        :return: A logger instance
        """
        if not self.__logger:
            cls = self.__class__
            self.__logger = logging.getLogger(
                cls.__module__ + "." + cls.__name__
            )

        return self.__logger

    def get_semantics(self):
        """
        Get a list of the semantics provided by the provider.  Subclasses
        must override this.

        :return: The list of semantics (list of strings which are the names
            of the semantics).
        """
        raise NotImplementedError()

    def create_semantic(self, spec, generator, constraint=None):
        """
        Create a value according to the given semantic spec.  For convenience,
        this default implementation tries to invoke a method named the same as
        the semantic name, except if the name contains hyphens.  If it contains
        hyphens, they are translated to underscores first, so it is easier to
        define the methods.  (Can't easily have a method name with a hyphen.)
        Subclasses can override this to do something else.

        :param spec: The semantic spec, which must be a mapping with a
            "semantics" property giving the name of the semantic.  Of course,
            that name should be one of the names returned by get_semantics()!
            Other properties may be used by the implementation, e.g. to
            influence how generation is done.
        :param generator: The generator through which this provider was
            invoked.  This allows implementations to delegate to other
            specifications as needed.  (But see the note in the class
            docstring.)
        :param constraint: A ValueConstraint instance representing some
            additional constraint to be honored by the generator.  This is
            derived from a co-constraint expression.  If None, there is no
            additional constraint.

        :return: The generated value
        """
        semantic = spec[SEMANTIC_PROPERTY_NAME].replace("-", "_")

        m = getattr(self, semantic)
        return m(spec, generator, constraint)


class FakerSemantics(SemanticsProvider):
    """
    A semantics provider which uses a faker.  The semantics names are taken
    directly from the faker object's providers' method names.  You can pass
    arguments into the faker method by adding additional properties to the
    specification.  They will be passed as keyword args.
    """

    def __init__(self, faker, faker_names=None):
        """
        Initialize this semantics provider.

        :param faker: The faker object to use
        :param faker_names: Iterable of names of faker methods to use from the
            given faker object, or None.  If None, the faker object's installed
            providers are scanned; this can result in a *lot* of names and a
            greater probability of semantic name collisions among semantics
            providers.
        """
        super().__init__()

        self.__faker = faker

        if faker_names:
            self.__semantics = list(faker_names)

            # Verify these names are valid faker methods?
            for name in self.__semantics:
                m = getattr(faker, name, None)
                if m is None:
                    # Or should this cause an exception...?
                    self.logger.warning(
                        "Faker function not found: %s", name
                    )

        else:

            # This is how faker finds methods from providers, as far as I could
            # tell from code inspection.  Faker also makes the methods
            # available directly on the faker object, but I still need to go
            # through the providers since a faker object has other methods
            # besides, and I wouldn't have a way of distinguishing.
            self.__semantics = [
                meth
                for prov in faker.get_providers()
                for meth in dir(prov)
                if not meth.startswith("_") and callable(getattr(prov, meth))
            ]

    def get_semantics(self):
        return self.__semantics

    def create_semantic(self, spec, generator, constraint=None):
        faker_kwargs = dict(spec)  # shallow-copy is ok

        # Remove stuff that's not part of the faker args, get desired
        # faker semantics name
        del faker_kwargs["type"]
        faker_semantics_name = faker_kwargs.pop(SEMANTIC_PROPERTY_NAME)

        faker_func = getattr(self.__faker, faker_semantics_name)
        return faker_func(**faker_kwargs)


class STIXSemantics(SemanticsProvider):
    """
    Some STIX-specific custom semantics.
    """

    SEMANTICS = [
        "stix-id",
        "stix-timestamp",
        "stix-pattern",
        "sha256",  # (conflicts with a Faker function)
        "sha512",
        "sha3_256",
        "sha3_512",
        "observable-container",
    ]

    _TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
    _TIMESTAMP_FORMAT_FRAC = "%Y-%m-%dT%H:%M:%S.%fZ"

    def get_semantics(self):
        return self.SEMANTICS

    def stix_id(self, spec, generator, constraint):
        """
        Create a STIX ID.  The spec requires the "stix-type" property, which
        determines the "<type>--" prefix.
        """
        if "stix-type" in spec:
            stix_type = spec["stix-type"]
            value = stix_type + "--" + str(uuid.uuid4())
        else:
            raise stix2generator.exceptions.ObjectGenerationError(
                'missing required "stix-type" property',
                spec[SEMANTIC_PROPERTY_NAME]
            )

        return value

    def stix_timestamp(self, spec, generator, constraint):
        """
        Create a random STIX timestamp which honors the given constraint.
        """
        if constraint:
            fmt = self._TIMESTAMP_FORMAT_FRAC if "." in constraint.value \
                else self._TIMESTAMP_FORMAT
            constraint_dt = datetime.datetime.strptime(constraint.value, fmt)
            constraint_dt = constraint_dt.replace(tzinfo=pytz.utc)

            if constraint.operator == constraint.EQ:
                timestamp_dt = constraint_dt

            else:
                equal_allowed = constraint.operator in (
                    constraint.GE, constraint.LE
                )

                # choose a random timestamp within a year of the constraint
                # timestamp...?
                random_duration = datetime.timedelta(
                    seconds=random.randint(
                        0 if equal_allowed else 1,
                        60 * 60 * 24 * 365 - 1
                    )
                )

                if constraint.operator in (constraint.LT, constraint.LE):
                    random_duration = -random_duration

                elif constraint.operator == constraint.NE:
                    if random.random() < 0.5:
                        random_duration = -random_duration

                # else for GE/GT, leave random_duration as-is

                timestamp_dt = constraint_dt + random_duration

        else:
            now_dt = datetime.datetime.now(tz=pytz.utc)

            # choose random within a year...?
            random_duration = datetime.timedelta(
                seconds=random.randint(
                    0,
                    60 * 60 * 24 * 365 - 1
                )
            )

            if random.random() < 0.5:
                random_duration = -random_duration

            timestamp_dt = now_dt + random_duration

        timestamp_str = timestamp_dt.strftime(self._TIMESTAMP_FORMAT)

        return timestamp_str

    def stix_pattern(self, spec, generator, constraint):
        """
        Create a random STIX pattern.
        """
        # Make kwargs from the spec, which we can use to create a pattern
        # generator Config object.  So configuring pattern generation is easy:
        # just use properties in the object generator spec which are named the
        # same as the Config settings for pattern generation.
        config_kwargs = dict(spec)
        config_kwargs.pop("type")
        config_kwargs.pop(SEMANTIC_PROPERTY_NAME)

        config = stix2generator.generation.pattern_generator.Config(
            **config_kwargs
        )
        patt_gen = stix2generator.generation.pattern_generator.PatternGenerator(
            generator, "2.1", config
        )

        pattern = patt_gen.generate()
        return pattern

    def _generate_hash(self, hash_function):
        """
        Generate a random hash using the given function.
        """
        value = hash_function(str(random.random()).encode())

        return value.hexdigest()

    def sha256(self, spec, generator, constraint):
        """
        Generate a random SHA256 hash.
        """
        return self._generate_hash(hashlib.sha256)

    def sha512(self, spec, generator, constraint):
        """
        Generate a random SHA512 hash.
        """
        return self._generate_hash(hashlib.sha512)

    def sha3_256(self, spec, generator, constraint):
        """
        Generate a random SHA3-256 hash.
        """
        return self._generate_hash(hashlib.sha3_256)

    def sha3_512(self, spec, generator, constraint):
        """
        Generate a random SHA3-512 hash.
        """
        return self._generate_hash(hashlib.sha3_512)

    def observable_container(self, spec, generator, constraint):
        """
        Generate an "observable container" object.  This is used as the value
        of the "objects" property of STIX 2.0-style observed-data objects.
        That property is deprecated in STIX 2.1.
        """

        config_kwargs = dict(spec)
        config_kwargs.pop("type")
        config_kwargs.pop(SEMANTIC_PROPERTY_NAME)

        config = stix2generator.generation.reference_graph_generator.Config(
            **config_kwargs
        )
        observable_container_generator = \
            stix2generator.generation.reference_graph_generator\
            .ReferenceGraphGenerator(generator, config)

        sco_type = stix2generator.utils.random_generatable_stix_type(
            generator, stix2generator.utils.STIXTypeClass.SCO
        )
        _, container = observable_container_generator.generate(sco_type)

        return container

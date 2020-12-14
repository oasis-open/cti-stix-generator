import itertools
import logging
import math
import random
import string

import stix2generator.generation
import stix2generator.generation.constraints
import stix2generator.generation.semantics

from stix2generator.exceptions import (
    CyclicSpecificationReferenceError, InvalidPropertyGroupError,
    ObjectGenerationError, PresenceCoconstraintError,
    SemanticValueTypeMismatchError, SpecificationNotFoundError,
    TypeMismatchError, UndefinedPropertyError, UnrecognizedJSONTypeError,
    ValueCoconstraintError
)


# lazy-initialized
_log = None


_NONE_TYPE = type(None)


# Legal values for the "type" property in specifications
# This and the values of _JSON_TYPE_MAP should of course be
# kept in sync.
_JSON_TYPES = {
    "string",
    "number",
    "integer",
    "boolean",
    "object",
    "array",
    "null"
}


# Used to infer a JSON type from a python type
_JSON_TYPE_MAP = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
    _NONE_TYPE: "null",
    dict: "object",
    list: "array"
}


class Config(stix2generator.generation.Config):
    """
    Simple config class for the ObjectGenerator.

    Most properties are self-explanatory.  Some notes:

    - The number settings apply to both "number" and "integer" specs

    - optional_property_probability is the probability of inclusion of
      optional properties.  Must be a number in [0, 1].

    - Setting minimize_ref_properties to True will cause the generator
      to attempt to minimize reference properties in generated objects,
      while still satisfying specification constraints.  If a reference
      property is necessary to satisfy a constraint, it will be included
      regardless of this setting.

      This setting overrides optional_property_probability for reference
      properties: if minimizing reference properties and
      optional_property_probability is 1 (meaning include all optional
      properties), optional reference properties may nevertheless be
      omitted.
    """

    _DEFAULTS = {
        "string_length_min": 5,
        "string_length_max": 20,
        "string_chars": string.ascii_letters,
        "number_min": -1000.0,
        "is_number_min_exclusive": False,
        "number_max": 1000.0,
        "is_number_max_exclusive": False,
        "array_length_min": 1,
        "array_length_max": 5,
        "optional_property_probability": 0.5,
        "minimize_ref_properties": True
    }


class ObjectGenerator:
    """
    Instances of this class generate JSON data from a specification.  More
    specifically, JSON-serializable Python structures are generated, which can
    be converted to JSON text.  So JSON objects are generated as dicts; arrays
    as lists, etc.
    """

    def __init__(
            self, spec_registry=None, semantic_providers=None, config=None
    ):
        """
        Initialize the generator.

        :param spec_registry: A name->specification mapping used to look
            up references inside of specifications
        :param semantic_providers: A list of semantic providers (e.g.
            instances of subclasses of SemanticsProvider)
        :param config: A Config instance giving user settings regarding
            generation.  If None, defaults will be used.
        """
        self.__specs = spec_registry or {}
        self.__config = config or Config()
        self.__semantics = {}

        # Create a map for fast lookup from a semantic name to its provider
        if semantic_providers:
            for provider in semantic_providers:
                semantics = provider.get_semantics()
                for semantic in semantics:
                    self.__semantics[semantic] = provider

    @property
    def config(self):
        """
        Get this generator's config object.
        """
        # If a public property, semantics implementations can use the config to
        # create values compatible with the invoking generator's settings.
        # Might be helpful?
        return self.__config

    @property
    def spec_names(self):
        """
        Get a read-only iterable view of this generator's supported spec
        names.

        :return: An iterable of spec names
        """
        return self.__specs.keys()

    def generate(
        self, spec_name, expected_type=None, spec_name_stack=None,
        value_constraint=None
    ):
        """
        Generate a value based on a specification identified by name.  The name
        is looked up in this generator's registry.

        :param spec_name: The specification name
        :param expected_type: If the named spec should produce a particular
            JSON type, that type.  If it doesn't matter, pass None.  This
            can be used to identify reference errors, where the reference is
            to a specification for the wrong type of thing.
        :param spec_name_stack: A stack of previously-visited specification
            names, used for reference loop detection.  Pass None to start a
            new stack.
        :param value_constraint: A ValueConstraint instance representing some
            additional constraint to be honored by the generator.  This is
            derived from a value co-constraint expression.  If None, there is
            no additional constraint.
        :return: The generated value
        :raises stix2generator.exceptions.CyclicSpecificationReferenceError:
            If a circular reference chain is detected
        :raises stix2generator.exceptions.SpecificationNotFoundError: If the
            named specification is not found in the registry
        :raises stix2generator.exceptions.ObjectGenerationError: For many other
            types of generation errors
        """

        if spec_name_stack is None:
            spec_name_stack = []

        # Reference loop check
        if spec_name in spec_name_stack:
            cycle = spec_name_stack[spec_name_stack.index(spec_name):]
            cycle.append(spec_name)
            raise CyclicSpecificationReferenceError(
                cycle, spec_name_stack=spec_name_stack[:]
            )

        if spec_name not in self.__specs:
            raise SpecificationNotFoundError(
                spec_name, spec_name_stack=spec_name_stack
            )

        spec = self.__specs[spec_name]

        try:

            spec_name_stack.append(spec_name)

            sdo_dict = self.generate_from_spec(
                spec, expected_type=expected_type,
                spec_name_stack=spec_name_stack,
                value_constraint=value_constraint
            )

            spec_name_stack.pop()

        except ObjectGenerationError as e:

            # In a recursive context, set this at the deepest nesting level
            # only
            if not e.spec_name_stack:
                e.spec_name_stack = spec_name_stack[:]  # a copy, to be safe

            raise

        return sdo_dict

    def generate_from_spec(
        self, spec, expected_type=None, spec_name_stack=None,
        value_constraint=None
    ):
        """
        Generate a value based on the given specification, which need not exist
        under any particular name in this generator's registry.

        :param spec: The specification, as parsed JSON
        :param expected_type: If the spec should be for a particular JSON type,
            that type.  If it doesn't matter, pass None.
        :param spec_name_stack: A stack of previously-visited specification
            names, used for reference loop detection.  Pass None to start a
            new stack.
        :param value_constraint: A ValueConstraint instance representing some
            additional constraint to be honored by the generator.  This is
            derived from a value co-constraint expression.  If None, there is
            no additional constraint.
        :return: The generated value
        :raises stix2generator.exceptions.UnrecognizedJSONTypeError: If given a
            non-const dict spec whose declared type is not recognized as a
            JSON type, or if expected_type is given and not a recognized JSON
            type.
        :raises stix2generator.exceptions.TypeMismatchError: If expected_type is
            given and the spec type doesn't match.
        :raises stix2generator.exceptions.ObjectGenerationError: For various
            ways the given spec is invalid.  Other types of errors are also
            wrapped/chained from this exception type (if possible) so that
            we get decoration with extra info from higher stack frames, which
            is useful for diagnosing where those problems occur.
        """

        spec_type = _get_spec_type(spec)

        if expected_type:
            if expected_type not in _JSON_TYPES:
                raise UnrecognizedJSONTypeError(expected_type)

            # There really should be some flexibility for numeric types: if
            # number is expected, integers should be accepted too...
            if spec_type != expected_type:
                raise TypeMismatchError(
                    expected_type, spec_type
                )

        # If not a dict, the spec IS the desired value.  It's an easy way to
        # produce fixed values.
        if not isinstance(spec, dict):
            value = spec

        # The other way: use "const", like in json-schema.
        elif "const" in spec:
            value = spec["const"]

        else:

            semantic_name = spec.get(
                stix2generator.generation.semantics.SEMANTIC_PROPERTY_NAME
            )

            try:

                if semantic_name:
                    value = self.__generate_semantic(spec, value_constraint)

                else:
                    value = self.__generate_plain(
                        spec, spec_name_stack, value_constraint
                    )

            except ObjectGenerationError as e:
                # In a recursive context, set this at the deepest nesting
                # level only.  Also, I think it's better to use the semantic
                # name as the type name in error messages, for semantic specs.
                if not e.spec_type:
                    e.spec_type = semantic_name or spec_type
                raise

            except Exception as e:
                raise ObjectGenerationError(
                    "An error occurred during generation: {}: {}".format(
                        type(e).__name__, str(e)
                    ),
                    semantic_name or spec_type
                ) from e

        return value

    def __generate_semantic(self, spec, value_constraint):
        """
        Generate from a semantic-type spec.

        :param spec: The spec
        :param value_constraint: A ValueConstraint instance representing some
            additional constraint to be honored by the generator.  This is
            derived from a value co-constraint expression.  If None, there is
            no additional constraint.
        :return: The generated value
        :raises stix2generator.exceptions.SemanticValueTypeMismatchError: If the
            semantic produces a value which doesn't agree with the spec's
            declared type.
        :raises stix2generator.exceptions.ObjectGenerationError: If the
            semantic name isn't found in any of this generator's semantic
            providers
        """
        semantic = spec[
            stix2generator.generation.semantics.SEMANTIC_PROPERTY_NAME
        ]

        if semantic in self.__semantics:
            provider = self.__semantics[semantic]

            value = provider.create_semantic(spec, self, value_constraint)

            # Should check that the implementation created the right type of
            # value.
            actual_type = _json_type_from_python_type(type(value))

            if actual_type != spec["type"]:
                raise SemanticValueTypeMismatchError(
                    semantic, actual_type, value, spec["type"]
                )

        else:
            raise ObjectGenerationError(
                "unrecognized semantic: " + semantic
            )

        return value

    def __generate_plain(self, spec, spec_name_stack, value_constraint):
        """
        Generate from a "plain" spec, i.e. one that isn't a semantic spec.
        Maybe not a very good method name... (Of course, the spec can have
        sub-specs or references to specs which are semantic.)

        :param spec: The "plain" spec
        :param spec_name_stack: Spec name stack, to propagate through
            references (if any)
        :param value_constraint: A ValueConstraint instance representing some
            additional constraint to be honored by the generator.  This is
            derived from a value co-constraint expression.  If None, there is
            no additional constraint.  This is *only* used to propagate through
            ref/oneOf specifications.  The "plain" generators (non-semantic)
            ignore constraints.
        :return: The generated value
        :raises stix2generator.exceptions.ObjectGenerationError: If a
            generation error occurs
        """
        type_ = spec["type"]

        if "ref" in spec:
            value = self.generate(
                spec["ref"],
                expected_type=type_,
                spec_name_stack=spec_name_stack,
                value_constraint=value_constraint
            )

        elif "oneOf" in spec:
            # value of the "oneOf" property should be a list of specs.
            sub_spec = random.choice(spec["oneOf"])
            value = self.generate_from_spec(
                sub_spec,
                expected_type=type_,
                spec_name_stack=spec_name_stack,
                value_constraint=value_constraint
            )

        else:
            generator = self.__GENERATOR_METHOD_MAP[type_]
            value = generator(self, spec, spec_name_stack)

        return value

    def generate_object(self, object_spec, spec_name_stack=None):
        """
        Generate a JSON object from the given specification.

        :param object_spec: A JSON object specification
        :param spec_name_stack: Specification name stack, for reference loop
            detection.  If None, use an empty stack.
        :return: A dict
        :raises stix2generator.exceptions.ObjectGenerationError: If a
            generation error occurs
        """

        # Handle imports
        if "import" in object_spec:
            imported_spec_name = object_spec["import"]
            gen_object = self.generate(
                imported_spec_name,
                expected_type="object",
                spec_name_stack=spec_name_stack
            )
        else:
            gen_object = {}

        # First, determine which properties to include
        names_to_include = _get_properties_to_include(
            object_spec, self.config.optional_property_probability,
            self.config.minimize_ref_properties
        )

        if names_to_include:
            # Then, find values for the included properties, according to their
            # specs and co-constraints.
            value_coconstraints = _get_value_coconstraints(object_spec)

            # At this point, if there were any names to include, there must
            # have been some properties defined!
            prop_specs = object_spec["properties"]
            for prop_name in names_to_include:

                # Generate constraint if necessary
                constraint = _get_value_constraint(
                    prop_name, value_coconstraints, gen_object
                )

                gen_object[prop_name] = self.generate_from_spec(
                    prop_specs[prop_name], spec_name_stack=spec_name_stack,
                    value_constraint=constraint
                )

        return gen_object

    def generate_array(self, array_spec, spec_name_stack=None):
        """
        Generate a JSON array from the given specification.

        :param array_spec: A JSON array specification
        :param spec_name_stack: Specification name stack, for reference loop
            detection.  If None, use an empty stack.
        :return: A list
        :raises stix2generator.exceptions.ObjectGenerationError: If a
            generation error occurs
        """

        item_spec = array_spec["items"]

        has_min = "minItems" in array_spec
        has_max = "maxItems" in array_spec

        if (has_min and not has_max) or (not has_min and has_max):
            raise ObjectGenerationError(
                "Specification must include both or neither of the properties: "
                "minItems, maxItems",
                "array"
            )

        min_items = array_spec.get("minItems", self.config.array_length_min)
        max_items = array_spec.get("maxItems", self.config.array_length_max)

        if min_items > max_items:
            raise ObjectGenerationError(
                "minItems must be less than or equal to maxItems",
                "array"
            )

        if min_items < 0 or max_items < 0:
            raise ObjectGenerationError(
                "minItems and maxItems must be non-negative: {}".format(
                    min_items if min_items < 0 else max_items
                ),
                "array"
            )

        array = [
            self.generate_from_spec(item_spec, spec_name_stack=spec_name_stack)
            for _ in range(
                random.randint(min_items, max_items)
            )
        ]

        return array

    def generate_string(self, string_spec, spec_name_stack=None):
        """
        Generate a string from the given specification.

        :param string_spec: A string specification
        :param spec_name_stack: A specification name stack, for reference loop
            detection.  Unused but included for API compatibility with
            object/array generators.
        :return: A string
        :raises stix2generator.exceptions.ObjectGenerationError: If a
            generation error occurs
        """

        has_min = "minLength" in string_spec
        has_max = "maxLength" in string_spec

        if (has_min and not has_max) or (not has_min and has_max):
            raise ObjectGenerationError(
                "Specification must include both or neither of the properties: "
                "minLength, maxLength",
                "string"
            )

        min_length = string_spec.get("minLength", self.config.string_length_min)
        max_length = string_spec.get("maxLength", self.config.string_length_max)

        if min_length > max_length:
            raise ObjectGenerationError(
                "minLength must be less than or equal to maxLength: {} <= {}"
                .format(min_length, max_length),
                "string"
            )

        if min_length < 0 or max_length < 0:
            raise ObjectGenerationError(
                "minLength and maxLength must be non-negative: {}".format(
                    min_length if min_length < 0 else max_length
                ),
                "string"
            )

        s = "".join(
            random.choice(self.config.string_chars)
            for _ in range(
                random.randint(min_length, max_length)
            )
        )

        return s

    def generate_integer(self, integer_spec, spec_name_stack=None):
        """
        Generate an integer from the given specification.

        :param integer_spec: An integer specification
        :param spec_name_stack: A specification name stack, for reference loop
            detection.  Unused but included for API compatibility with
            object/array generators.
        :return: An int
        :raises stix2generator.exceptions.ObjectGenerationError: If a
            generation error occurs
        """
        min_, is_min_exclusive, max_, is_max_exclusive = \
            _process_numeric_min_max_properties(
                integer_spec,
                self.config.number_min,
                self.config.is_number_min_exclusive,
                self.config.number_max,
                self.config.is_number_max_exclusive
            )

        # Guess I won't assume the user expressed the bounds as ints, so I
        # need to convert to ints and check the resulting bounds.  The
        # call above to process min/max properties doesn't assume we require
        # ints.
        if int(min_) == min_:
            min_ = int(min_)
            if is_min_exclusive:
                min_ += 1
        else:
            min_ = int(math.ceil(min_))

        if int(max_) == max_:
            max_ = int(max_)
            if is_max_exclusive:
                max_ -= 1
        else:
            max_ = int(math.floor(max_))

        if min_ > max_:
            raise ObjectGenerationError(
                "no integers exist in the specified interval",
                "integer"
            )

        return random.randint(min_, max_)

    def generate_number(self, number_spec, spec_name_stack=None):
        """
        Generate a number (float) from the given specification.

        :param number_spec: A number specification
        :param spec_name_stack: A specification name stack, for reference loop
            detection.  Unused but included for API compatibility with
            object/array generators.
        :return: A float
        :raises stix2generator.exceptions.ObjectGenerationError: If a
            generation error occurs
        """

        min_, is_min_exclusive, max_, is_max_exclusive = \
            _process_numeric_min_max_properties(
                number_spec,
                self.config.number_min,
                self.config.is_number_min_exclusive,
                self.config.number_max,
                self.config.is_number_max_exclusive
            )

        if is_min_exclusive and is_max_exclusive:
            n = _random_open(min_, max_)
        elif is_min_exclusive:
            n = _random_half_open_lower(min_, max_)
        elif is_max_exclusive:
            n = _random_half_open_upper(min_, max_)
        else:
            n = _random_closed(min_, max_)

        return n

    def generate_boolean(self, boolean_spec, spec_name_stack=None):
        """
        Generate a boolean from the given specification.

        :param boolean_spec: A boolean specification (ignored; there's nothing
            to configure for now)
        :param spec_name_stack: A specification name stack, for reference loop
            detection.  Unused but included for API compatibility with
            object/array generators.
        :return: True or False
        """
        if random.random() < 0.5:
            return True
        return False

    def generate_null(self, null_spec, spec_name_stack=None):
        """
        Generate null (None).

        :param null_spec: A null specification (ignored; there's nothing
            to configure for now)
        :param spec_name_stack: A specification name stack, for reference loop
            detection.  Unused but included for API compatibility with
            object/array generators.
        :return: None
        """
        return None

    # This has to be at the bottom, after the methods are defined.  Would it
    # have been better to store method names and use getattr() to get the
    # methods instead?  Or generate a function name from a template?  This is
    # yet another map to keep sync'd up with others.  Think about ways of
    # improving this situation...
    __GENERATOR_METHOD_MAP = {
        "object": generate_object,
        "array": generate_array,
        "string": generate_string,
        "integer": generate_integer,
        "number": generate_number,
        "boolean": generate_boolean,
        "null": generate_null
    }


def _get_logger():
    global _log
    if _log is None:
        _log = logging.getLogger(__name__)

    return _log


def _get_value_coconstraints(object_spec):
    """
    Get the value coconstraints, if any, from the given object specification.
    This also does some error checking.

    :param object_spec: The object specification whose value coconstraints
        should be checked.
    :return: A list of ValueCoconstraint objects; will be empty if there are
        none defined.
    :raises stix2generator.exceptions.ValueCoconstraintError: If an
        invalid value co-constraint is found.
    """

    # This function shouldn't be called if object_spec has no properties, but
    # just in case...
    assert "properties" in object_spec

    value_coconstraints = object_spec.get("value-coconstraints", [])
    prop_specs = object_spec["properties"]
    coconstraint_objs = []

    for coconstraint in value_coconstraints:
        coconstraint_obj = \
            stix2generator.generation.constraints.make_value_coconstraint(
                coconstraint
            )

        coconstraint_objs.append(coconstraint_obj)

        if coconstraint_obj.prop_name_left not in prop_specs:
            raise ValueCoconstraintError(
                coconstraint,
                "Property '{}' undefined in specification".format(
                    coconstraint_obj.prop_name_left
                )
            )

        if coconstraint_obj.prop_name_right not in prop_specs:
            raise ValueCoconstraintError(
                coconstraint,
                "Property '{}' undefined in specification".format(
                    coconstraint_obj.prop_name_right
                )
            )

    # Another scan through the coconstraints to check for properties
    # referenced more than once.
    prop_occurrence_counts = {}

    def inc_count_for_key(d, k):
        count = d.setdefault(k, 0) + 1
        d[k] = count

    for coconstraint_obj in coconstraint_objs:
        inc_count_for_key(
            prop_occurrence_counts,
            coconstraint_obj.prop_name_left
        )

        inc_count_for_key(
            prop_occurrence_counts,
            coconstraint_obj.prop_name_right
        )

    props_with_count_gt_1 = [
        k for k, v in prop_occurrence_counts.items()
        if v > 1
    ]

    if props_with_count_gt_1:
        log = _get_logger()
        log.warning(
            "Some properties are referenced in more than one value"
            " co-constraint.  If such a property requires constraining based on"
            " another property value, only the first such co-constraint will be"
            " consulted: %s", ", ".join(props_with_count_gt_1)
        )

    return coconstraint_objs


def _check_property_groups(groups_spec, property_specs):
    """
    Do some sanity checks on the given property groups: empty groups,
    bad property names, naming conflicts, etc.  Runs for side-effects
    (exceptions) and doesn't return anything.

    :param groups_spec: The groups spec from a presence coconstraint
        specification from an object specification
    :param property_specs: The properties specifications from an object
        specification
    :raises stix2generator.exceptions.InvalidPropertyGroupError: If
        there is a problem with a property group
    """
    for group_name, prop_names in groups_spec.items():

        if not prop_names:
            raise InvalidPropertyGroupError(
               group_name, "group can't be empty"
            )

        if group_name in property_specs:
            raise InvalidPropertyGroupError(
                group_name, "group name conflicts with a property name"
            )

        undef_props = set(prop_names) - property_specs.keys()
        if undef_props:
            raise InvalidPropertyGroupError(
                group_name, 'undefined property(s): {}'.format(
                    ", ".join(undef_props)
                )
            )

    # check pairwise intersections to ensure all groups are disjoint
    if len(groups_spec) > 1:
        for group1, group2 in itertools.combinations(groups_spec, 2):
            overlaps = set(groups_spec[group1]) & set(groups_spec[group2])
            if overlaps:
                raise InvalidPropertyGroupError(
                    group2,
                    'overlaps with group "{}".  Overlapping properties: {}'
                    .format(
                        group1,
                        ", ".join(overlaps)
                    )
                )


def _get_group_coconstraints(presence_coconstraints, property_specs):
    """
    Get property group co-constraints from the presence co-constraint
    part of an object specification.

    Length 1 property groups will have some sanity checking done, but
    will otherwise be ignored.  That is better accomplished by using the
    property directly instead of putting it in its own group.

    :param presence_coconstraints: The presence co-constraints dict from an
        object specification.
    :param property_specs: The property definitions dict from an object
        specification.
    :return: A mapping of group name to
        stix2generator.generation.constraints.PresenceCoconstraint object
        representing the group co-constraint.  If there were no property
        groups defined, the map will be empty.
    :raises stix2generator.exceptions.PresenceCoconstraintError: If an invalid
        presence co-constraint is found
    """

    # Should map group names to lists of property names (group contents)
    group_specs = presence_coconstraints.get("property-groups", {})

    # Sanity check groups
    _check_property_groups(group_specs, property_specs)

    all_of_groups = set(presence_coconstraints.get("all", []))
    one_of_groups = set(presence_coconstraints.get("one", []))
    at_least_one_of_groups = set(
        presence_coconstraints.get("at-least-one", [])
    )

    # Sanity check for bad group names in constraint type lists
    for group_name in itertools.chain(
        all_of_groups, one_of_groups, at_least_one_of_groups
    ):
        if group_name not in group_specs:
            raise PresenceCoconstraintError(
                "Group not found: " + group_name
            )

    # Ensure no group is assigned more than one constraint type
    constraint_conflicts = set()
    for groups1, groups2 in itertools.combinations((
        all_of_groups, one_of_groups, at_least_one_of_groups
    ), 2):
        constraint_conflicts |= groups1 & groups2

    if constraint_conflicts:
        raise PresenceCoconstraintError(
            "Property group(s) have conflicting co-constraints: {}".format(
                ", ".join(constraint_conflicts)
            )
        )

    # Define a default constraint type, or require that every group be
    # explicitly assigned one?  Maybe being explicit is clearer?  So check for
    # groups which weren't assigned constraint types.
    unassigned_groups = group_specs.keys() - all_of_groups - \
        one_of_groups - at_least_one_of_groups
    if unassigned_groups:
        raise PresenceCoconstraintError(
            "Property group(s) were not assigned co-constraint types: "
            "{}".format(
                ", ".join(unassigned_groups)
            )
        )

    # Filter out length-1 groups.  I think I'd like the above checks to be done
    # on them anyway, to avoid silly specifications, but here we will start
    # ignoring them.
    groups_to_ignore = []
    for group_name, property_names in group_specs.items():
        if len(property_names) == 1:
            groups_to_ignore.append(group_name)

    group_specs = dict(group_specs)  # shallow copy ok
    for group_name in groups_to_ignore:
        del group_specs[group_name]

    constraint_objs = {
        group_name: stix2generator.generation.constraints.PresenceCoconstraint(
            property_names,
            "one" if group_name in one_of_groups
            else "all" if group_name in all_of_groups
            else "at-least-one"
        )
        for group_name, property_names in group_specs.items()
    }

    return constraint_objs


def _get_dependency_coconstraints(presence_coconstraints, group_coconstraints,
                                  property_specs):
    """
    Get dependency co-constraints, which is part of the presence co-constraints.
    This just does a lot of sanity checks on the dependencies object from the
    spec.

    :param presence_coconstraints:
    :param group_coconstraints:
    :param property_specs:
    :return: The dependency co-constraints object.  If none was given, returns
        an empty dict.
    :raises stix2generator.exceptions.PresenceCoconstraintError: If an invalid
        presence co-constraint is found
    """

    deps = presence_coconstraints.get("dependencies", {})

    grouped_property_names = set(
        itertools.chain.from_iterable(
            coco.property_names
            for coco in group_coconstraints.values()
        )
    )

    def is_group_or_prop(name):
        return name in property_specs or name in group_coconstraints

    for key_name, prop_list in deps.items():
        if not is_group_or_prop(key_name):
            raise PresenceCoconstraintError(
                "Unrecognized group or property: " + key_name
            )

        if key_name in grouped_property_names:
            raise PresenceCoconstraintError(
                'Property "{}" is grouped and cannot be referenced'
                ' individually'.format(key_name)
            )

        for name in prop_list:

            if not is_group_or_prop(name):
                raise PresenceCoconstraintError(
                    "Unrecognized group or property: " + name
                )

            if name in grouped_property_names:
                raise PresenceCoconstraintError(
                    'Property "{}" is grouped and cannot be referenced'
                    ' individually'.format(name)
                )

            if name in deps:
                raise PresenceCoconstraintError(
                    "Dependency key can't also occur in a dependency"
                    " value: " + name
                )

    return deps


def _get_presence_coconstraints(object_spec):
    """
    Get presence co-constraint info from the given object specification.
    This includes the groups and dependencies.

    :param object_spec: The object specification
    :return: A 2-tuple with (a) the group co-constraint mapping from group
        name to constraint object, and the dependencies mapping from property
        or group name to list of properties/groups.
    :raises stix2generator.exceptions.PresenceCoconstraintError: If an invalid
        presence co-constraint is found
    """

    presence_coconstraints = object_spec.get("presence-coconstraints", {})
    property_specs = object_spec.get("properties", {})

    group_coconstraints = _get_group_coconstraints(
        presence_coconstraints, property_specs
    )

    dependency_coconstraints = _get_dependency_coconstraints(
        presence_coconstraints, group_coconstraints, property_specs
    )

    return group_coconstraints, dependency_coconstraints


def _get_properties_to_include(
        object_spec, optional_property_probability, minimize_ref_properties
):
    """
    Determine which object properties to include, based on required/optional
    choices and any defined presence co-constraints.

    :param object_spec: The object spec
    :param optional_property_probability: The probability an optional property
        should be included.  Must be a number from 0 to 1.
    :param minimize_ref_properties: True if we should minimize optional
        reference properties.  False if they should receive no special
        treatment.
    :return: The property names, as a set of strings
    :raises stix2generator.exceptions.PresenceCoconstraintError: If an invalid
        presence co-constraint is found
    :raises stix2generator.exceptions.UndefinedPropertyError: If a reference to an
        undefined property or group is found in the "required" or "optional"
        property value of the spec
    :raises stix2generator.exceptions.ObjectGenerationError: If a reference to a
        grouped property is found
    """

    prop_specs = object_spec.get("properties", {})
    required_names = object_spec.get("required")
    optional_names = object_spec.get("optional")

    if required_names is not None and optional_names is not None:
        raise ObjectGenerationError(
            '"required" and "optional" can\'t both be present'
        )

    # If neither optional nor required names are specified, all
    # properties/groups will be required.
    elif required_names is None and optional_names is None:
        # empty optional set = all required
        optional_names = set()

    # Convert to sets to remove dupes
    elif required_names is not None:
        required_names = set(required_names)
    elif optional_names is not None:
        optional_names = set(optional_names)

    group_coconstraints, dependency_coconstraints = \
        _get_presence_coconstraints(object_spec)

    # Detect errors in the required/optional prop list: all must be
    # defined, and grouped properties must not be referenced
    req_or_opt = required_names if required_names is not None \
        else optional_names
    defined_prop_names = prop_specs.keys()
    defined_group_names = group_coconstraints.keys()
    grouped_property_names = set(
        itertools.chain.from_iterable(
            coco.property_names
            for coco in group_coconstraints.values()
        )
    )

    undef_name_errors = req_or_opt - defined_prop_names - defined_group_names
    if undef_name_errors:
        raise UndefinedPropertyError(undef_name_errors)

    grouped_prop_errors = req_or_opt & grouped_property_names
    if grouped_prop_errors:
        raise ObjectGenerationError(
            "Property(s) are grouped and cannot be referenced"
            " individually: {}".format(
                ", ".join(
                    "{}".format(p) for p in grouped_prop_errors
                )
            )
        )

    # Include all ungrouped property names and property group names in
    # the same "pool" of names one can specify as required or optional.
    name_pool = (defined_prop_names - grouped_property_names) \
        | defined_group_names

    # Get set of optional names (whether they specified "required" or
    # "optional" in the spec).
    effectively_optional_names = optional_names if optional_names is not None \
        else name_pool - required_names

    # Start out the set of names to include with all required ones.
    names_to_include = required_names if required_names is not None \
        else name_pool - effectively_optional_names

    # And then maybe add some optional ones.
    for name in effectively_optional_names:

        is_group = name in defined_group_names
        is_ref = name.endswith("_ref") or name.endswith("_refs")

        can_include = False
        if minimize_ref_properties:
            if is_group:
                if group_coconstraints[name].can_satisfy_without_refs():
                    can_include = True
            elif not is_ref:
                can_include = True

        else:
            can_include = True

        if can_include and random.random() < optional_property_probability:
            names_to_include.add(name)

    # Incorporate the "dependencies": add any other properties we
    # require
    for dep_key, dep_names in dependency_coconstraints.items():
        if dep_key in names_to_include:
            names_to_include.update(dep_names)

    # For any names which are property groups, expand them to the
    # component properties according to their co-constraints
    # ... can't modify a set as you iterate!  So need a temp set.
    temp_set = set()
    for name in names_to_include:
        if name in group_coconstraints:
            temp_set.update(
                group_coconstraints[name].choose_properties(
                    optional_property_probability,
                    minimize_ref_properties
                )
            )
        else:
            temp_set.add(name)

    names_to_include = temp_set

    return names_to_include


def _get_value_constraint(prop_name, coconstraints, partially_generated_object):
    """
    Get a value constraint object derived from a value co-constraint involving
    the given property.

    :param prop_name: The property to check for co-constraints
    :param coconstraints: An iterable of co-constraint objects
        (stix2generator.generation.constraints.ValueCoconstraint)
    :param partially_generated_object: The object being generated, in its
        current state of partial construction.  This is necessary to find the
        value of the other property involved in the co-constraint, if any.
    :return: A constraint object
        (stix2generator.generation.constraints.ValueConstraint) representing a
        necessary constraint on the given property, or None if no constraint is
        necessary.
    """
    constraint = None
    for coconstraint in coconstraints:
        if coconstraint.involves_property(prop_name):
            other_prop_name = coconstraint.get_other_property(
                prop_name
            )
            if other_prop_name in partially_generated_object:
                constraint = coconstraint.get_constraint(
                    other_prop_name,
                    partially_generated_object[other_prop_name]
                )

            break

    return constraint


def _json_type_from_python_type(python_type):
    """
    Infers a JSON type from a python type.  This is necessary for reference
    verification when the type isn't explicitly given (e.g. a "const" spec).

    :param python_type: The python type (a 'type' object)
    :return: A JSON type name
    :raises stix2generator.exceptions.ObjectGenerationError: If a JSON type can't
        be inferred from python_type
    """
    json_type = _JSON_TYPE_MAP.get(python_type)
    if json_type is None:
        raise ObjectGenerationError(
            "Can't infer JSON type from " + str(python_type)
        )

    return json_type


def _get_spec_type(spec):
    """
    Determine the type of the given spec, as one of the supported JSON
    types.

    :param spec: A specification
    :return: A spec JSON type as a string, e.g. "string", "array", etc.
    :raises stix2generator.exceptions.ObjectGenerationError: If a const spec
        where the spec type can't be inferred from the constant; if a
        non-const spec whose "type" property is missing
    :raises stix2generator.exceptions.UnrecognizedJSONTypeError: if the value of
        the "type" property isn't a recognized JSON type
    """
    if isinstance(spec, dict):
        if "const" in spec:
            # type is implied by the value of the "const" property.
            value_type = type(spec["const"])
            json_type = _json_type_from_python_type(value_type)

        elif "type" in spec:
            json_type = spec["type"]
            if json_type not in _JSON_TYPES:
                raise UnrecognizedJSONTypeError(json_type)

        else:
            raise ObjectGenerationError(
                '"type" property is missing'
            )

    else:
        # the spec is the value.  Check its type.
        value_type = type(spec)
        json_type = _json_type_from_python_type(value_type)

    return json_type


def _process_numeric_min_max_properties(
    spec,
    default_min,
    is_default_min_exclusive,
    default_max,
    is_default_max_exclusive
):
    """
    Factors out a rather large chunk of code for validating and processing
    the min/max properties on numbers and integers.  Maybe we need a
    JSON-Schema for specifications and validate against that, to reduce the
    amount of hand-written validation code we need to write...

    :param spec: A number or integer spec
    :param default_min: If the spec doesn't specify a minimum, use this as
        the default.
    :param is_default_min_exclusive: Whether default_min, if it is used,
        is an exclusive bound.
    :param default_max: If the spec doesn't specify a maximum, use this as
        the default.
    :param is_default_max_exclusive: Whether default_max, if it is used,
        is an exclusive bound.
    :return: A (num, bool, num, bool) 4-tuple giving the bounds and whether
        each bound is exclusive or not:
            (min, is_min_exclusive, max, is_max_exclusive)
    :raises stix2generator.exceptions.ObjectGenerationError: For various types
        of problems with numeric specifications
    """
    if "minimum" in spec and "exclusiveMinimum" in spec:
        raise ObjectGenerationError(
            "minimum and exclusiveMinimum can't both be present"
        )

    if "maximum" in spec and "exclusiveMaximum" in spec:
        raise ObjectGenerationError(
            "maximum and exclusiveMaximum can't both be present"
        )

    min_given = any(
        p in spec
        for p in ("minimum", "exclusiveMinimum")
    )
    max_given = any(
        p in spec
        for p in ("maximum", "exclusiveMaximum")
    )

    # I think this check is necessary since user-specified min/max could well
    # be out of order w.r.t. defaults, producing unexpected errors.  What would
    # users expect the other bound to be anyway, if they only gave one bound?
    if (min_given and not max_given) or (max_given and not min_given):
        raise ObjectGenerationError(
            "can't give minimum without a maximum, or vice versa"
        )

    if "minimum" in spec:
        min_ = spec["minimum"]
        is_min_exclusive = False
    elif "exclusiveMinimum" in spec:
        min_ = spec["exclusiveMinimum"]
        is_min_exclusive = True
    else:
        min_ = default_min
        is_min_exclusive = is_default_min_exclusive

    if "maximum" in spec:
        max_ = spec["maximum"]
        is_max_exclusive = False
    elif "exclusiveMaximum" in spec:
        max_ = spec["exclusiveMaximum"]
        is_max_exclusive = True
    else:
        max_ = default_max
        is_max_exclusive = is_default_max_exclusive

    if min_ > max_:
        raise ObjectGenerationError(
            "minimum can't be greater than maximum"
        )
    elif min_ == max_ and (is_max_exclusive or is_min_exclusive):
        raise ObjectGenerationError(
            "In an open or half-open interval, minimum must be strictly "
            "less than maximum"
        )

    return min_, is_min_exclusive, max_, is_max_exclusive


def _random_half_open_upper(min_, ex_max):
    assert min_ < ex_max

    # easy case... I think, since random.random() already has the right
    # openness.
    n = min_ + (ex_max - min_) * random.random()

    return n


def _random_half_open_lower(ex_min, max_):
    assert ex_min < max_

    # harder case: we compute the opposite openness, then "flip" it by
    # negating the result.  So for example, [a,b) becomes (-b,-a].  That
    # gives us the correct openness and range, but wrong endpoints.  Then, we
    # just "shift" the interval to its proper endpoints.  That's one way of
    # looking at it, at least.
    n = ex_min + max_ - _random_half_open_upper(ex_min, max_)

    return n


def _random_closed(min_, max_):
    assert min_ <= max_

    # Python gives us a simple API which is documented to use a closed
    # interval, but the same docs say that one endpoint may or may not actually
    # be included... so maybe this doesn't actually work?  It actually quotes
    # the exact same equation I used in _random_half_open_upper()!
    return random.uniform(min_, max_)


def _random_open(ex_min, ex_max):
    assert ex_min < ex_max

    # It's not obvious how to have a uniformly distributed open interval.  I
    # had an idea to add two intervals of opposite openness covering the same
    # range and divide by 2, to obtain a totally open interval.  E.g. to get
    # (0, 1) compute ([0, 1) + (0, 1]) / 2.  I think this yields an open
    # interval, but at the expense of uniformity.
    # n = _random_half_open_upper(ex_min, ex_max) + \
    #     _random_half_open_lower(ex_min, ex_max)
    # n /= 2.0

    # Another idea is to split an open interval into two half-open intervals
    # which are joined at a closed boundary in the middle.  This implies that
    # the mid point is slightly more likely than other points, so this isn't
    # uniform either, but I think it's better than above.  Perhaps it's close
    # enough??
    mid = (ex_min + ex_max) / 2.0
    if random.random() < 0.5:
        n = _random_half_open_lower(ex_min, mid)
    else:
        n = _random_half_open_upper(mid, ex_max)

    return n

    # Another possibility I found on stackoverflow was essentially to generate
    # a random positive integer (1 to something big, to give a lot of possible
    # distinct generated numbers) and divide by a number slightly larger than
    # the maximum.  https://stackoverflow.com/a/19934205

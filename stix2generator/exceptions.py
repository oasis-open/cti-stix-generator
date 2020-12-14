import stix2generator.utils


class GenerationError(Exception):
    """
    Base class for all object and graph generation (via the prototyping
    language) errors.
    """
    pass


class RegistryNotFoundError(GenerationError):
    """
    Represents failure to find an object generator specification registry for
    the given STIX version.
    """
    def __init__(self, stix_version):
        super().__init__(
            "Object specification registry not found for STIX version "
            + stix_version
        )

        self.stix_version = stix_version


class LanguageError(GenerationError):
    """
    Base class for exceptions thrown while processing the STIX prototyping
    language.  Instances may have line/column attributes giving the location
    of the error, if known/applicable.
    """
    def __init__(self, message, parse_tree_meta=None):
        """
        Initialize this error.  If metadata is given, it will be used to
        decorate the message with additional line/column number information.
        The line and column information will also be assigned to same-named
        properties of the exception object.

        :param message: The error message.
        :param parse_tree_meta: Metadata from the parse tree which contains
            line/column number information.  This must be an object with
            "line" and "column" attributes, or None if that information is not
            known or applicable.
        """

        if parse_tree_meta:
            self.line = parse_tree_meta.line
            self.column = parse_tree_meta.column
            message = "{}:{}: {}".format(
                self.line, self.column, message
            )
        else:
            self.line = self.column = None

        super().__init__(message)


class VariableError(LanguageError):
    """
    Instances of this class represent errors regarding variable usage.
    """
    def __init__(self, message, var_name, parse_tree_meta=None):
        """
        Initialize this error.  The name of the variable will be available as
        the var_name property of the exception object.

        :param message: The error message
        :param var_name: The name of the variable.  If this is a Lark Token
            object, it can act as the metadata; parse_tree_meta is not
            necessary in that case.  If parse_tree_meta is given, it takes
            priority.
        :param parse_tree_meta: Metadata from the parse tree, or None.
            See LanguageError for a description of this parameter.
        """
        name_is_token = stix2generator.utils.is_token(var_name)
        if parse_tree_meta is None and name_is_token:
            parse_tree_meta = var_name

        super().__init__(message, parse_tree_meta)

        self.var_name = var_name.value if name_is_token else var_name


class UndeclaredVariableError(VariableError):
    """
    Instances of this class represent use of an undeclared variable.
    """
    def __init__(self, var_name, parse_tree_meta=None):
        """
        Initialize this error.

        :param var_name: The name of the undeclared variable.  See
            VariableError for more description of this parameter.
        :param parse_tree_meta: Metadata from the parse tree, or None.
            See LanguageError for a description of this parameter.
        """
        message = "Undeclared variable: " + var_name
        super().__init__(
            message, var_name, parse_tree_meta
        )


class RedeclaredVariableError(VariableError):
    """
    Instances of this class represent the declaration of a variable more
    than once.
    """
    def __init__(self, var_name, parse_tree_meta=None):
        """
        Initialize this error.

        :param var_name: The name of the redeclared variable.  See
            VariableError for more description of this parameter.
        :param parse_tree_meta: Metadata from the parse tree, or None.
            See LanguageError for a description of this parameter.
        """
        message = "Redeclared variable: " + var_name
        super().__init__(
            message, var_name, parse_tree_meta
        )


class CircularVariableDependenciesError(LanguageError):
    """
    Instances of this class represent circular dependencies among variables.
    """
    def __init__(self, path):
        """
        Initialize this error.  The path will be available as the same-named
        property of the exception object.

        :param path: A list of strings which gives the circular variable
            dependency path which was found.
        """
        super().__init__(
            "Circular dependency detected in variable declarations: "
            + " > ".join(path)
        )

        self.path = path


class ObjectGenerationError(GenerationError):
    """
    Base class for object generation errors.  Also used directly as a raised
    exception type, when there isn't a more specific object generation error
    subclass that's applicable.  This is typically used for various types of
    problems with specifications.

    This class is written (and used) in a different way, to make it easier to
    have good error messages.  I think there is a relatively common problem in
    exception handling, that at the point where an exception object is created,
    not all contextual information is known.  Python's default behavior
    requires that a complete message be generated at the point the exception
    object is constructed.  When you don't have all the contextual information
    at that point, it's just impossible to generate a good message.  That makes
    it tempting to pass extra context junk into functions/methods which is only
    used to generate decent error messages.  In simple cases, that may be fine,
    but in excess, it can clutter the API.

    An approach to improving the situation is to allow an exception to have
    some extra info added as it propagates through stack frames where that
    info is known.  I first came across this idea in Boost years ago, and I
    decided to try a similar design here.  My idea is that exception handlers
    can specifically add specification type and name info, if known, as the
    exception propagates.  Then I override how the message is formatted to
    incorporate this additional information.
    """

    def __init__(self, message, spec_type=None, spec_name_stack=None):
        """
        Initialize the exception.

        :param message: The base exception message (no need to include spec
            type or name information in the message; you can pass those in
            separately and the message will be augmented to include that info
            in a standard way).
        :param spec_type: A spec type if known/applicable, or None if not.
            E.g. a JSON type or semantic name.
        :param spec_name_stack: A spec name or list of names if
            known/applicable, or None if not.  This describes a chain of
            references.  For convenience, a plain name will be treated as a
            length-1 list.
        """

        super().__init__(message)

        self.__message = message

        # attrs for exception handlers to set
        self.spec_type = spec_type
        if isinstance(spec_name_stack, str):
            self.spec_name_stack = [spec_name_stack]
        else:
            self.spec_name_stack = spec_name_stack or []

    def __str__(self):
        """
        Overrides the base class's exception message generation.  This uses
        the spec name/type attrs to improve the message, if they were set.
        """
        msg_parts = []
        if self.spec_name_stack:
            stack_desc = " > ".join(
                "'{}'".format(name) for name in self.spec_name_stack
            )

            msg_parts.append(
                "In specification {}: ".format(stack_desc)
            )

        if self.spec_type:
            msg_parts.append(
                "Error generating {}: ".format(self.spec_type)
            )

        msg_parts.append(self.__message)

        return "".join(msg_parts)


class UnrecognizedJSONTypeError(ObjectGenerationError):
    """
    Represents an unrecognized spec type, e.g. in a spec's "type" property.
    """
    def __init__(self, spec_type, spec_name_stack=None):

        super().__init__(
            "unrecognized JSON type", spec_type, spec_name_stack
        )


class CyclicSpecificationReferenceError(ObjectGenerationError):
    """
    Instances represent a reference cycle composed of specification names.
    """
    def __init__(self, spec_name_cycle, spec_type=None, spec_name_stack=None):

        message = "Specification reference cycle detected: " + \
            " > ".join(spec_name_cycle)

        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.spec_name_cycle = spec_name_cycle


class TypeMismatchError(ObjectGenerationError):
    """
    Instances represent a spec type mismatch: a spec for a particular JSON
    type was required, but a spec for a different type was found instead.
    """
    def __init__(self, expected_type, actual_type, spec_type=None,
                 spec_name_stack=None):

        message = "Type mismatch: expected '{}' but got '{}'".format(
            expected_type, actual_type
        )

        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.expected_type = expected_type
        self.actual_type = actual_type


class SemanticValueTypeMismatchError(ObjectGenerationError):
    """
    Instances represent a mismatch between the type of value produced by a
    semantic implementation, and the declared type of a specification.
    """

    def __init__(self, semantic_name, actual_type, actual_value, spec_type,
                 spec_name_stack=None):

        message = "Semantic '{}' produced a value of the wrong type: " \
                  "expected {}, got {}: {}".format(
                      semantic_name, spec_type, actual_type, actual_value
                  )

        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.semantic_name = semantic_name
        self.actual_type = actual_type
        self.actual_value = actual_value


class SpecificationNotFoundError(ObjectGenerationError):
    """
    A specification referred to by name was not found in the registry.
    """
    def __init__(self, spec_name, spec_type=None, spec_name_stack=None):

        message = "Spec not found: '{}'".format(spec_name)

        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.spec_name = spec_name


class UndefinedPropertyError(ObjectGenerationError):
    """
    Instances represent a reference outside a co-constraint to a property which
    was not defined in an object specification.  (Inside a co-constraint, a
    different co-constraint error type is used, to indicate a bad
    co-constraint.)
    """
    def __init__(self, prop_names, spec_type=None, spec_name_stack=None):

        # Support a single string as well, converting to a list
        if isinstance(prop_names, str):
            prop_names = [prop_names]

        message = "Reference to undefined property(s): " + \
                  ", ".join(prop_names)
        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.prop_names = prop_names


class ValueCoconstraintError(ObjectGenerationError):
    """
    Instances represent an invalid value co-constraint.
    """
    def __init__(self, coconstraint, message, spec_type=None,
                 spec_name_stack=None):

        message = "Invalid value co-constraint '{}': {}".format(
            coconstraint,
            message
        )

        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.coconstraint = coconstraint


class PresenceCoconstraintError(ObjectGenerationError):
    """
    Instances represent an invalid presence co-constraint.
    """
    pass


class InvalidPropertyGroupError(PresenceCoconstraintError):
    """
    Instances represent an invalid property group, within a presence
    co-constraint definition.
    """
    def __init__(self, group_name, message, spec_type=None,
                 spec_name_stack=None):

        message = 'Invalid property group "{}": {}'.format(group_name, message)
        super().__init__(
            message, spec_type, spec_name_stack
        )

        self.group_name = group_name


class GeneratableSTIXTypeNotFoundError(GenerationError):
    """
    Instances of this class represent inability to find a generator spec
    registered with an object generator, which satisfies particular
    STIX-related criteria.  For example, we might require any SDO or SCO type.
    """
    def __init__(self, constraints, stix_version):
        """
        Initialize this exception instance.

        :param constraints: The constraints which failed to match any
            specification.  Must be a list of constraint values.  See
            stix2generator.utils.random_generatable_stix_type() or
            .is_stix_type() for more information.
        :param stix_version: The STIX version which the constraints were
            checked relative to
        """

        message = "Could not find an object generator specification for a " \
                  "STIX {} type satisfying the constraints: {}".format(
                      stix_version,
                      constraints
                  )
        super().__init__(message)

        self.constraints = constraints
        self.stix_version = stix_version


class PatternGenerationError(GenerationError):
    """
    Base class for errors related to random STIX pattern generation.
    """
    pass


class UnhandledPropertyValueType(PatternGenerationError):
    """
    Instances represent an unhandled property value type from a stix2 object.
    The property value is used to create a constant in a STIX pattern, and we
    need to know what comparison expression operators are legal to use with it.
    """
    def __init__(self, value):
        message = "Can't create comparison expression: don't know what " \
                  "operators apply to type {}: {}".format(
                      type(value).__name__, str(value)
                  )
        super().__init__(message)

        self.value = value


class UnsupportedObjectStructureError(PatternGenerationError):
    """
    The AST for object paths can't represent arbitrary path structure.  E.g. it
    can't represent a list of lists.  Instances of this class represent a
    random path taken through a STIX object, where the path contains
    unsupported structure.
    """
    def __init__(self, object_type, path_elements):
        message = "The path through a '{}' contains unsupported structure:" \
                  " {}".format(
                      object_type, repr(path_elements)
                  )
        super().__init__(message)

        self.object_type = object_type
        self.path_elements = path_elements


class UnrecognizedSTIXTypeError(PatternGenerationError):
    """
    Instances represent a STIX SCO type given as a comparison expression type
    constraint, which was unrecognized.  A generator spec could not be found
    which generates objects of that type.
    """
    def __init__(self, stix_type):
        message = "Unrecognized STIX type for comparison expression type" \
                  " constraint: {}".format(stix_type)
        super().__init__(message)

        self.stix_type = stix_type


class InvalidRefPropertyValueError(PatternGenerationError):
    """
    Instances represent an invalid value for a reference property.  The value
    must be an ID from which we can extract an object type, which is used to
    continue an object path through the reference.
    """
    def __init__(self, value):
        message = "Invalid reference property value, must be an" \
                  " object ID: {}".format(value)

        super().__init__(message)
        self.value = value


class AutoRegistrationError(Exception):
    """
    Base class for errors with automatic creation and registration of
    Python classes as stix2 custom objects, which are derived from object
    generator specifications.
    """
    def __init__(self, message, spec_name=None):
        super().__init__(message)

        self.__message = message
        self.spec_name = spec_name

    def __str__(self):
        msg_parts = []
        if self.spec_name:
            msg_parts.append(
                "In specification {}: ".format(self.spec_name)
            )

        msg_parts.append(self.__message)

        return "".join(msg_parts)


class AutoRegistrationInferenceError(AutoRegistrationError):
    """
    For auto-registration to work, STIX object information must be inferred
    from an object generator specification.  Instances of this class represent
    situations where the spec is such that inference can't be performed (even
    if the spec itself is valid).
    """
    pass


class IllegalSTIXObjectSpecType(AutoRegistrationInferenceError):
    """
    Specifications for STIX objects must be of type "object".
    """

    def __init__(self, spec_type, spec_name=None):
        message = 'STIX object specs must have type "object"; got "{}"'.format(
            spec_type
        )
        super().__init__(message, spec_name)

        self.spec_type = spec_type


class IllegalSTIXObjectPropertyType(AutoRegistrationInferenceError):
    """
    An object generator property spec was for a JSON type which is unsupported
    for use as a stix2 property type.
    """
    def __init__(self, prop_type, spec_name=None):
        message = 'Don\'t know how to make a stix2 property object for ' \
                  'spec type "{}"'.format(prop_type)
        super().__init__(message, spec_name)

        self.prop_type = prop_type


class EmptyListError(AutoRegistrationInferenceError):
    def __init__(self):
        message = "Can't infer a list type from an empty list.  The list's " \
                  "element type must be inferrable, so it needs at least one " \
                  "value."
        super().__init__(message)


class HeterogenousListError(AutoRegistrationInferenceError):
    def __init__(self, list_):
        message = "Can't infer a list element type from a heterogenous " \
                  "list: " + str(list_)
        super().__init__(message)

        self.list_ = list_

import random
import re

import stix2generator.exceptions
import stix2generator.utils


class ValueConstraintOperators:
    """
    A mixin/base-class for the constraint classes, which contains some
    convenience constants et al for operators.
    """

    # Legal operators
    EQ, NE, GT, GE, LT, LE = OPERATORS = range(6)

    # Reversed operators, aligned with OPERATORS such that the reverse of
    # OPERATORS[i] is REVERSE_OPERATORS[i].  (EQ and NE are symmetric, so they
    # are their own reverses.)
    REVERSE_OPERATORS = EQ, NE, LT, LE, GT, GE

    STRING_OPERATOR_MAP = {
        "=": EQ,
        "!=": NE,
        ">": GT,
        ">=": GE,
        "<": LT,
        "<=": LE
    }

    OPERATOR_STRING_MAP = {
        v: k
        for (k, v) in STRING_OPERATOR_MAP.items()
    }

    @staticmethod
    def to_operator(operator):
        """
        Normalize a value to an operator constant.  If a string is passed,
        convert it to an operator constant.  Otherwise, assume it is already
        an operator constant and just return it unchanged.

        :param operator: An operator string or operator constant
        :return: An operator constant
        """
        if isinstance(operator, str):
            return ValueConstraintOperators.STRING_OPERATOR_MAP[operator]
        else:
            return operator


class ValueConstraint(ValueConstraintOperators):
    """
    Represents a constraint on a property.  E.g. that it be less than some
    value.  Currently this just consists of an operator and a value.  The
    relationship to the property to be constrained is maintained externally,
    so it is not stored in these instances.
    """

    def __init__(self, operator, value):
        self.operator = self.to_operator(operator)
        self.value = value

    def __str__(self):
        return "{} {}".format(
            self.OPERATOR_STRING_MAP[self.operator],
            self.value
        )


class ValueCoconstraint(ValueConstraintOperators):
    """
    Represents a co-constraint between two properties.  This just stores two
    property names and an operator.  When the value of one property becomes
    known, a constraint can be derived for the other property.
    """

    def __init__(self, prop_name_left, operator, prop_name_right):
        self.operator = self.to_operator(operator)
        self.prop_name_left = prop_name_left
        self.prop_name_right = prop_name_right

    def get_constraint(self, prop_name, prop_value):
        """
        Given the value of one property of this co-constraint, derive a
        constraint on the other.

        :param prop_name: The name of one property of this co-constraint
        :param prop_value: The value of prop_name
        :return: A ValueConstraint object representing a constraint on the other
            property.
        :raises ValueError: If the property name given isn't a part of this
            co-constraint.
        """
        if prop_name == self.prop_name_left:
            constraint = ValueConstraint(
                self.REVERSE_OPERATORS[self.operator],
                prop_value
            )

        elif prop_name == self.prop_name_right:
            constraint = ValueConstraint(self.operator, prop_value)

        else:
            # Leave this as a ValueError instead of a ObjectGenerationError
            # subclass.  This error would be the result of an internal bug
            # (i.e. should not happen in a correctly-working library).  Should
            # there be a special InternalError exception class?
            raise ValueError(
                "Property name '{}' not present in coconstraint '{}'".format(
                    prop_name, self
                )
            )

        return constraint

    def involves_property(self, prop_name):
        return prop_name in (self.prop_name_right, self.prop_name_left)

    def get_other_property(self, prop_name):
        if prop_name == self.prop_name_right:
            return self.prop_name_left
        return self.prop_name_right

    def __str__(self):
        return "{} {} {}".format(
            self.prop_name_left,
            self.OPERATOR_STRING_MAP[self.operator],
            self.prop_name_right
        )


class PresenceCoconstraint:

    ONE, ALL, AT_LEAST_ONE = range(3)

    STRING_CONSTRAINT_TYPE_MAP = {
        "one": ONE,
        "all": ALL,
        "at-least-one": AT_LEAST_ONE
    }

    CONSTRAINT_TYPE_STRING_MAP = {
        v: k
        for (k, v) in STRING_CONSTRAINT_TYPE_MAP.items()
    }

    def __init__(self, property_names, constraint_type):
        self.constraint_type = self.to_constraint_type(constraint_type)
        self.property_names = set(property_names)  # dedupes property names

    @staticmethod
    def to_constraint_type(constraint_type):
        if isinstance(constraint_type, str):
            return PresenceCoconstraint.STRING_CONSTRAINT_TYPE_MAP[
                constraint_type
            ]
        else:
            return constraint_type

    def choose_properties(self, probability, minimize_ref_properties):
        """
        Choose some properties from the group, according to its constraint
        type.

        :param probability: This is used only for the at-least-one constraint
            type.  For that type, one is randomly chosen as the required
            property; the rest are optional and included with this probability.
        :param minimize_ref_properties: Modify how property selection is done:
            if True, minimize reference properties in the selection.  Reference
            properties may still be chosen, if there is no other way to
            satisfy the constraint.
        :return: A list of property names.
        """
        assert self.property_names, "Property group must not be empty!"

        non_ref_prop_names = [
            name for name in self.property_names
            if not _is_ref_prop(name)
        ]

        if self.constraint_type == self.ONE:
            if minimize_ref_properties and non_ref_prop_names:
                chosen_props = [random.choice(non_ref_prop_names)]
            else:
                # Or should I have just stored the names as a list...?
                chosen_props = [
                    stix2generator.utils.rand_iterable(self.property_names)
                ]

        elif self.constraint_type == self.AT_LEAST_ONE:

            # Choose one required prop; make the rest optional.  If minimizing
            # reference properties and all are reference properties, we should
            # behave like "one" and choose exactly one.  Choosing more would
            # not be "minimal".
            if minimize_ref_properties and non_ref_prop_names:
                required_prop = random.choice(non_ref_prop_names)
            else:
                required_prop = stix2generator.utils.rand_iterable(
                    self.property_names
                )

            chosen_props = [required_prop]
            candidate_other_props = \
                non_ref_prop_names if minimize_ref_properties \
                else self.property_names

            chosen_props.extend(
                prop for prop in candidate_other_props
                if prop != required_prop and random.random() < probability
            )

        else:
            # ALL
            chosen_props = list(self.property_names)

        return chosen_props

    def can_satisfy_without_refs(self):
        """
        Determine whether it is possible to satisfy this presence co-constraint
        with only non-reference properties.
        """

        if self.constraint_type in (self.ONE, self.AT_LEAST_ONE):
            result = any(not _is_ref_prop(name) for name in self.property_names)

        else:
            # ALL
            result = all(not _is_ref_prop(name) for name in self.property_names)

        return result

    def __str__(self):
        # On python2, this produces the weird set syntax: set(["a","b",...])
        # Should I care about that?
        return "{} {}".format(
            self.CONSTRAINT_TYPE_STRING_MAP[self.constraint_type],
            self.property_names
        )


def _is_ref_prop(name):
    """Determine whether the given name names a "reference" property."""
    return name.endswith("_ref") or name.endswith("_refs")


# This regex just splits a string into an operator and the stuff to its
# left and right.  Trying to avoid a full-fledged parser for this.  It's more
# complicated since I want to avoid an expression like "a!=b" being
# accidentally misinterpreted as "a!" = "b", or "a<=b" misinterpreted as
# "a" < "=b".  So the stuff on the left and right is defined as one or more
# non-operator characters.  The operator starts at the first operator
# character.  An "operator character" is any character appearing in an
# operator.  Operators have symbology which is unlikely to appear in a property
# name, so I hope this is sufficient for now.
_OP_CHARS = "".join(set("".join(ValueConstraintOperators.STRING_OPERATOR_MAP)))
_VALUE_COCONSTRAINT_RE = re.compile(
    "^([^{0}]+)({1})([^{0}]+)$".format(
        re.escape(_OP_CHARS),
        "|".join(
            re.escape(op) for op in ValueConstraintOperators.STRING_OPERATOR_MAP
        )
    ),
    re.S
)


def make_value_coconstraint(value_coconstraint_expr):
    """
    Make a ValueCoconstraint object from a co-constraint expression.  The
    expression syntax is simple: <prop_name> <op> <prop_name>.  E.g. "a < b".

    :param value_coconstraint_expr: The expression, as a string
    :return: The ValueCoconstraint object
    :raises ValueError: if the expression is invalid
    """

    match = _VALUE_COCONSTRAINT_RE.match(value_coconstraint_expr)
    if not match:
        raise stix2generator.exceptions.ValueCoconstraintError(
            value_coconstraint_expr,
            "Invalid expression syntax"
        )

    prop_name_left = match.group(1).strip()
    operator = match.group(2)
    prop_name_right = match.group(3).strip()

    if prop_name_right == prop_name_left:
        raise stix2generator.exceptions.ValueCoconstraintError(
            value_coconstraint_expr,
            "Can't relate a property to itself"
        )

    return ValueCoconstraint(prop_name_left, operator, prop_name_right)

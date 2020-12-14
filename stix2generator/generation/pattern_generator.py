import collections.abc
import datetime
import logging
import random
import stix2
import stix2.parsing
import stix2.utils
import stix2generator
from stix2generator.exceptions import (
    UnhandledPropertyValueType, SpecificationNotFoundError,
    UnsupportedObjectStructureError, UnrecognizedSTIXTypeError,
    InvalidRefPropertyValueError
)
import stix2generator.generation
import stix2generator.utils


# Don't create object paths which include the following properties.
_OBJECT_PATH_BLACKLIST = {
    "id",
    "type",
    "spec_version"
}


# Maps types we would find as property values of stix2 objects, to the
# operators we may use them with in a comparison expression.
_PYTHON_TYPE_TO_OPERATORS = {
    int: ("<", "<=", ">", ">=", "=", "!="),
    float: ("<", "<=", ">", ">=", "=", "!="),
    str: ("<", "<=", ">", ">=", "=", "!="),
    stix2.utils.STIXdatetime: ("<", "<=", ">", ">=", "=", "!="),
    bool: ("=", "!="),
}


# stix2's AST uses a different class for each comparison operator.  Use this
# to resolve an operator to the corresponding AST class.
_OPERATOR_TO_AST_CLASS = {
    "<": stix2.LessThanComparisonExpression,
    "<=": stix2.LessThanEqualComparisonExpression,
    ">": stix2.GreaterThanComparisonExpression,
    ">=": stix2.GreaterThanEqualComparisonExpression,
    "=": stix2.EqualityComparisonExpression,
    "!=": stix2.EqualityComparisonExpression,
    # "!=" uses the same EqualityComparisonExpression class, just constructed
    # differently, so it will have to be a special case.
}


# Represents list index "star" steps in object paths
_INDEX_STAR_STEP = object()


class Config(stix2generator.generation.Config):
    """
    STIX pattern generator config settings.

    min/max_pattern_size: Bounds on pattern size, in terms of the total number
        of simple comparison expressions across all observation expressions.

    min/max_repeat_count: bounds on the repeat count for the REPEATS qualifier.

    min/max_within_count: bounds on the number of seconds for the WITHIN
        qualifier.

    probability_qualifier: Probability a given observation expression (at any
        nesting level) will get a random qualifier.

    probability_continue_path_through_ref: When randomly generating an object
        path, determines how likely the path will continue through a reference
        property to another object.

    probability_index_star_step: When randomly generating an object path,
        determines how likely list index steps will use '*'.
    """
    _DEFAULTS = {
        "min_pattern_size": 1,
        "max_pattern_size": 5,
        "min_repeat_count": 1,
        "max_repeat_count": 10,
        "min_within_count": 1,
        "max_within_count": 10,
        "probability_qualifier": 0.2,
        "probability_continue_path_through_ref": 0.8,
        "probability_index_star_step": 0.1
    }


def _rand_series(n):
    """
    Generate a random series (sum) which adds to 'n'.  The generated series
    takes the form of a sequence of positive integers which add to n.  If
    n <= 0, nothing is generated.

    :param n: The desired sum, as an integer
    """
    # With this algorithm, the probability distribution over series is not
    # uniform: it favors shorter series over longer ones.  Should I try to
    # think of something better?
    while n > 0:
        k = random.randint(1, n)
        yield k
        n -= k


def _random_operator_for_type(type_):
    """
    Pick a random comparison expression "operator" for the given type.  In
    fact, there is a different AST class for (most) comparison expression
    operators, so we must actually choose a random class instead.

    There is no class corresponding to "!="; it is realized with the class for
    equality, and with a flag for negation.  So we must actually return both a
    class and a boolean indicating whether to negate.

    :param type_: A type, e.g. int, str, etc
    :return: A 2-tuple consisting of (1) an AST class, and (2) a boolean
        negation value, or None if the type is unrecognized and a set of legal
        operators can't be determined.
    """
    candidate_ops = _PYTHON_TYPE_TO_OPERATORS.get(type_)
    if not candidate_ops:
        return None

    op = random.choice(candidate_ops)
    ast_class = _OPERATOR_TO_AST_CLASS[op]

    # Special case... there is no AST class for not-equal.  Instead, it uses
    # EqualityComparisonExpression with a flag for negation.
    negated = op == "!="

    return ast_class, negated


def _is_ref_path(path_elements):
    """
    Determine whether the given object path, expressed as an element list
    (see _element_list_to_object_path()), ends with a reference and is
    therefore eligible for continuation through the reference.  The given
    object path is assumed to be "completed" down to a single STIX property
    value.  This means that a *_ref property will be the last component, and
    *_refs will be second-to-last, because it requires a subsequent index step.

    :param path_elements: An object path, as a list
    :return: True if a continuable reference path; False if not
    """
    result = False
    if path_elements:
        last_elt = path_elements[-1]
        if isinstance(last_elt, str) and last_elt.endswith("_ref"):
            result = True

        elif len(path_elements) > 1:
            # for _refs properties, the ref property itself must be
            # second-to-last, and the last path element must be an index step,
            # either "*" or an int.  Maybe not necessary to check the index
            # step; all we need is to check the second-to-last property.
            second_last_elt = path_elements[-2]
            if isinstance(second_last_elt, str) \
                    and second_last_elt.endswith("_refs"):
                result = True

    return result


def _element_list_to_object_path(object_type, path_elements):
    """
    Build an AST ObjectPath instance from an object "path" given as a list
    of strings, ints and the special _INDEX_STAR_STEP object, used for list
    index "star" steps.  The strings are interpreted as property names and
    the ints/star steps as list indices.

    :param object_type: The SCO type to use for the ObjectPath instance
    :param path_elements: The path elements as a list of
        strings/ints/_INDEX_STAR_STEPs
    :return: An ObjectPath instance
    """

    path_components = []
    i = 0
    while i < len(path_elements):
        elt_i = path_elements[i]

        if not isinstance(elt_i, str):
            raise UnsupportedObjectStructureError(
                object_type, path_elements
            )

        if i < len(path_elements) - 1:
            elt_i1 = path_elements[i+1]
            if isinstance(elt_i1, int):
                component = stix2.ListObjectPathComponent(elt_i, elt_i1)
                i += 1

            elif elt_i1 is _INDEX_STAR_STEP:
                component = stix2.ListObjectPathComponent(elt_i, "*")
                i += 1

            # ignoring ReferenceObjectPathComponent here.  I think the pattern
            # visitor never uses it(?), so I guess I won't either.

            else:
                component = stix2.BasicObjectPathComponent(elt_i, False)

        else:
            component = stix2.BasicObjectPathComponent(elt_i, False)

        path_components.append(component)
        i += 1

    object_path = stix2.ObjectPath(object_type, path_components)

    return object_path


class PatternGenerator:
    """
    Instances of this class generate random STIX patterns.
    """

    def __init__(self, object_generator, stix_version, config=None):
        """
        Initialize this PatternGenerator.  Patterns are generated by randomly
        walking through randomly generated objects, so a pattern generator
        relies on an object generator for its random STIX content.

        :param object_generator: A STIX object generator
        :param stix_version: The STIX version to generate patterns for.  (This
            should probably match up with the version of objects generated by
            object_generator!)
        :param config: A Config object with settings for pattern generation,
            or None to choose default settings
        """
        cls = self.__class__
        self.__log = logging.getLogger(
            cls.__module__ + "." + cls.__name__
        )

        self.__generator = object_generator
        self.__stix_version = stix_version
        self.__config = config or Config()

    def __random_sco_type(self):
        return stix2generator.utils.random_generatable_stix_type(
            self.__generator,
            stix2generator.utils.STIXTypeClass.SCO,
            stix_version=self.__stix_version
        )

    def __generate_object_path(self, type_constraint=None):
        """
        Generate a random object path.  This is done by generating a random
        object, and then choosing a random path through it.  If type_constraint
        is given, an object of that type is generated.  Otherwise, a random SCO
        type is chosen.  The value at the "end" of the path is also returned,
        for use in the pattern.

        :param type_constraint: An SCO type, or None
        :return: A 2-tuple consisting of (1) the ObjectPath instance, and (2)
            a value from the object.  This value will be taken from a stix2
            object, so that determines its type.  It could be a string,
            STIXdatetime instance, etc.
        """
        if type_constraint:
            sco_type = type_constraint
        else:
            sco_type = self.__random_sco_type()

        try:
            obj_dict = self.__generator.generate(sco_type)
        except SpecificationNotFoundError as e:
            raise UnrecognizedSTIXTypeError(sco_type) from e

        obj = stix2.parse(obj_dict, allow_custom=True)

        path_elements = []
        while True:
            if isinstance(obj, collections.abc.Mapping):
                candidate_props = obj.keys() - _OBJECT_PATH_BLACKLIST
                element = stix2generator.utils.rand_iterable(candidate_props)
            elif isinstance(obj, list):
                element = random.randrange(len(obj))
            else:
                break

            # Let's have a chance to append an index "star" step when a
            # list is encountered, instead of the chosen index.
            if isinstance(element, int) and \
                    random.random() < self.__config.probability_index_star_step:
                path_elements.append(_INDEX_STAR_STEP)
            else:
                path_elements.append(element)

            obj = obj[element]

        object_path = _element_list_to_object_path(sco_type, path_elements)

        if _is_ref_path(path_elements) and \
                random.random() < \
                self.__config.probability_continue_path_through_ref:

            # If a ref path, the value must be an ID.  Extract the object type
            # from the ID and generate a path of that type to concatenate to our
            # path.  In this way, we can continue the path through references.
            dd_idx = obj.find("--")
            if dd_idx == -1:
                raise InvalidRefPropertyValueError(obj)

            id_type = obj[:dd_idx]

            try:
                path_continuation, obj = self.__generate_object_path(id_type)
            except UnrecognizedSTIXTypeError:
                # We couldn't generate an SCO of type id_type.  Reduce this to
                # a warning; we will simply not have a continued path in this
                # case.
                self.__log.warning(
                    'Truncating object path due to unrecognized SCO type "%s"',
                    id_type
                )

            else:
                object_path.property_path.extend(
                    path_continuation.property_path
                )

        return object_path, obj

    def __generate_simple_comparison_expression(self, type_constraint=None):
        """
        Generate a "simple" <path> <op> <value> comparison expression.  If
        a type constraint is given, that will be the SCO type for the path.
        Otherwise, a random SCO type is chosen.

        :param type_constraint: An SCO type, or None
        :return: An AST instance for a simple comparison expression
        """

        object_path, value = self.__generate_object_path(type_constraint)

        result = _random_operator_for_type(type(value))
        if result is None:
            raise UnhandledPropertyValueType(value)

        ast_class, negated = result
        ast_node = ast_class(object_path, value)
        ast_node.negated = negated

        return ast_node

    def __generate_simple_comparison_expression_list(
        self, size, type_constraint, is_and
    ):
        """
        Generate a list of the given size of "simple" comparison expressions,
        which honors the given type constraint, relative to the indicated
        boolean connective.  is_and indicates how the returned comparison
        expressions will be used.  They will be connected with 'AND' if is_and
        is True, else 'OR'.  Therefore, if a type constraint is given and
        is_and is True, all generated comparison expressions must be of the
        given type.  Otherwise, at least one must be of the given type.  If no
        type constraint is given then is_and must be False, because AND'd
        comparison expressions require a constraint.  If is_and is False and
        no type constraint is given, all comparison expressions will be of
        randomly chosen types.

        :param size: The number of simple comparison expressions to generate
        :param type_constraint: An SCO type, or None
        :param is_and: True if the returned expressions will be connected via
            AND; False if they will be connected via OR.
        :return: The list of comparison expressions (ASTs).
        """
        assert size >= 0

        # If AND, all operands *must* be type-constrained.
        assert not is_and or type_constraint

        if type_constraint:
            if is_and:
                # In 'AND': all simple exprs must be of the same type
                result = [
                    self.__generate_simple_comparison_expression(
                        type_constraint
                    )
                    for _ in range(size)
                ]

            else:
                # In 'OR': at least one must be of the constraining type.

                # Create N-1 unconstrained exprs and 1 constrained expr...
                if size == 0:
                    result = []

                else:
                    result = [
                        self.__generate_simple_comparison_expression(None)
                        for _ in range(size-1)
                    ]

                    constrained_expr = \
                        self.__generate_simple_comparison_expression(
                            type_constraint
                        )

                    # Then insert the constrained one at a random location in
                    # the list
                    result.insert(
                        random.randint(0, len(result)),
                        constrained_expr
                    )

        else:
            # no type constraint; must be an 'OR'.  So we can generate whatever
            # types we want.
            result = [
                self.__generate_simple_comparison_expression(
                    None
                )
                for _ in range(size)
            ]

        return result

    def __generate_complex_comparison_expression(
        self, size, type_constraint=None
    ):
        """
        Generates a "complex" comparison expression, i.e. one which may consist
        of sub-expressions connected via AND or OR.  If a type constraint is
        given, the resulting expression will honor that constraint.

        :param size: The size of the desired complex comparison expression, in
            terms of the number of simple comparison expressions it must contain
        :param type_constraint: An SCO type, or None
        :return:
        """
        assert size > 0

        # This complex expression must be composed of N simple expressions.
        # This implementation builds the overall expression in two parts: a
        # left and right side.  The location of the split between left and
        # right is random.  A side is randomly chosen to just contain a series
        # of simple expressions, and the other side will have a nested
        # subexpression.
        #
        # One goal of the strategy is to avoid excessive nested parentheses.
        # Too many parentheses results in ugly crazy-looking patterns.  This
        # algorithm still can generate some silly patterns, but I hope it helps
        # a little.
        if size == 1:
            expr = self.__generate_simple_comparison_expression_list(
                1, type_constraint, False
            )[0]

        else:

            # Choose whether top-level operator will be AND or OR.
            # This will also determine how we handle the type constraint.
            is_and = random.random() < 0.5

            # If AND, all operands *must* be type-constrained.
            if is_and and not type_constraint:
                type_constraint = self.__random_sco_type()

            # In the following, if type_constraint is None, both left and right
            # constraints will be None.  No need for a special case.  If we
            # have a type constraint, for 'AND', the constraint must be
            # enforced on both sides.  For 'OR', we need only enforce it on one
            # side.
            if is_and:
                left_constraint = right_constraint = type_constraint
            else:
                left_constraint, right_constraint = type_constraint, None
                if random.random() < 0.5:
                    left_constraint, right_constraint = \
                        right_constraint, left_constraint

            # Don't let either side be zero size here.  Avoids the case where
            # we have an OR, and randomly choose to enforce the type constraint
            # on the zero-length side.  That can result in an invalid pattern.
            lsize = random.randint(1, size-1)
            rsize = size - lsize

            if random.random() < 0.5:
                # Parenthesize right case
                operands = self.__generate_simple_comparison_expression_list(
                    lsize, left_constraint, is_and
                )

                operands.append(stix2.ParentheticalExpression(
                    self.__generate_complex_comparison_expression(
                        rsize, right_constraint
                    )
                ))

            else:
                # Parenthesize left case
                operands = [stix2.ParentheticalExpression(
                    self.__generate_complex_comparison_expression(
                        lsize, left_constraint
                    )
                )]

                operands.extend(
                    self.__generate_simple_comparison_expression_list(
                        rsize, right_constraint, is_and
                    )
                )

            if is_and:
                expr = stix2.AndBooleanExpression(operands)
            else:
                expr = stix2.OrBooleanExpression(operands)

        return expr

    def __generate_random_qualifier(self):
        """
        Generate a random qualifier AST object.

        :return: The qualifier object
        """
        qual_type = random.randrange(3)

        if qual_type == 0:
            repeat_count = random.randint(
                self.__config.min_repeat_count,
                self.__config.max_repeat_count
            )
            qualifier = stix2.RepeatQualifier(repeat_count)

        elif qual_type == 1:
            within_count = random.randint(
                self.__config.min_within_count,
                self.__config.max_within_count
            )
            qualifier = stix2.WithinQualifier(within_count)

        else:
            # Let's make the random timestamps near the current time
            # (within a year).
            dur1 = datetime.timedelta(
                microseconds=random.randrange(
                    # 1 year
                    1000000 * 60 * 60 * 24 * 365
                )
            )

            dur2 = datetime.timedelta(
                microseconds=random.randrange(
                    # 1 year
                    1000000 * 60 * 60 * 24 * 365
                )
            )

            if random.random() < 0.5:
                dur1 = -dur1

            if random.random() < 0.5:
                dur2 = -dur2

            now = datetime.datetime.utcnow()
            dt1 = now + dur1
            dt2 = now + dur2

            # Order them as start=dt1, stop=dt2
            if dt1 > dt2:
                dt1, dt2 = dt2, dt1

            elif dt1 == dt2:
                # in the remote chance we get the same timestamp for both,
                # just nudge one ahead...
                dt2 += datetime.timedelta(seconds=1)

            # STIX 2.0 requires string constants and millisecond precision
            # here...
            if self.__stix_version == "2.0":
                dt1_str = stix2.utils.format_datetime(
                    stix2.utils.STIXdatetime(dt1, precision="millisecond")
                )
                dt1 = stix2.patterns.StringConstant(dt1_str)

                dt2_str = stix2.utils.format_datetime(
                    stix2.utils.STIXdatetime(dt2, precision="millisecond")
                )
                dt2 = stix2.patterns.StringConstant(dt2_str)

            qualifier = stix2.StartStopQualifier(dt1, dt2)

        return qualifier

    def __generate_observation_expression(self, size):
        """
        Generate a random complex observation expression, which may consist of
        sub-expressions and qualifiers.

        :param size: The size of the desired observation expression, in terms of
            the number of simple comparison expressions it must contain
        :return: The observation expression AST
        """
        assert size > 0

        # The generation strategy is similar to that for comparison expressions
        # (see __generate_complex_comparison_expression()).  It is generated in
        # two parts of random size; one side is constructed as a sub-expression.

        if size == 1:
            obs_expr = stix2.ObservationExpression(
                self.__generate_complex_comparison_expression(1)
            )

        else:
            lsize = random.randint(0, size)
            rsize = size - lsize

            if random.random() < 0.5:
                # Parenthesize right case
                obs_exprs = [
                    stix2.ObservationExpression(
                        self.__generate_complex_comparison_expression(sz)
                    )
                    for sz in _rand_series(lsize)
                ]

                if rsize > 0:
                    obs_exprs.append(stix2.ParentheticalExpression(
                        self.__generate_observation_expression(rsize)
                    ))

            else:
                # Parenthesize left case
                if lsize == 0:
                    obs_exprs = []
                else:
                    obs_exprs = [stix2.ParentheticalExpression(
                        self.__generate_observation_expression(lsize)
                    )]

                obs_exprs.extend(
                    stix2.ObservationExpression(
                        self.__generate_complex_comparison_expression(sz)
                    )
                    for sz in _rand_series(rsize)
                )

            ast_class = random.choice((
                stix2.AndObservationExpression,
                stix2.OrObservationExpression,
                stix2.FollowedByObservationExpression
            ))

            obs_expr = ast_class(obs_exprs)

        if random.random() < self.__config.probability_qualifier:
            qualifier = self.__generate_random_qualifier()
            obs_expr = stix2.QualifiedObservationExpression(obs_expr, qualifier)

        return obs_expr

    def generate_ast(self):
        """
        Generate a random STIX pattern as an AST.

        :return: A pattern AST
        """

        size = random.randint(
            self.__config.min_pattern_size,
            self.__config.max_pattern_size
        )

        return self.__generate_observation_expression(size)

    def generate(self):
        """
        Generate a random STIX pattern.

        :return: A pattern string
        """

        pattern_ast = self.generate_ast()
        return str(pattern_ast)

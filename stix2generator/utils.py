import collections.abc
import random
import lark
import stix2.registry
import stix2.utils


def is_tree(node, rule_name=None):
    """
    Determine whether the given parse tree node is a Tree node, and optionally
    verify its type.

    :param node: The node to check
    :param rule_name: A node type, or None if it doesn't matter
    :return: True if the node is a Tree node of the proper type, False
        otherwise.
    """
    return isinstance(node, lark.Tree) and (
        rule_name is None or node.data == rule_name
    )


def is_token(node, token_type=None):
    """
    Determine whether the given parse tree node is a Token node, and optionally
    verify its type.

    :param node: The node to check
    :param token_type: A token type, or None if it doesn't matter
    :return: True if the node is a Token node of the proper type, False
        otherwise.
    """
    return isinstance(node, lark.Token) and (
        token_type is None or node.type == token_type
    )


def rand_iterable(it, len_it=None):
    """
    Choose a uniformly random value from the given iterable.  If len(it) is
    available, len_it may be None.  Otherwise, len_it must be provided as the
    "length" of the given iterable (the number of values which will be
    produced).

    random.choice() seems to require a sequence (needs indexed access), so it
    doesn't work with things like sets.

    :param it: The iterable
    :param len_it: The length of it, or None to obtain the length via len().
    :return: A random value from it
    """
    if len_it is None:
        len_it = len(it)

    for i, val in enumerate(it):
        if random.random() < 1.0 / (len_it - i):
            return val

    raise Exception("Iterable was empty!")


def recurse_references(obj):
    """
    Helper for find_references().  See that function for more information.
    Can also be used as a more generic reference finder, which requires no
    particular structure (e.g. a "type" property) and has no special casing for
    observed-data/objects.

    :param obj: An object.  Can be any type, but values will only be produced
        from mappings.
    """
    if isinstance(obj, collections.abc.Mapping):
        for prop, value in obj.items():
            if prop.endswith("_ref"):
                yield prop, value

            elif prop.endswith("_refs"):
                for ref in value:
                    yield prop, ref

            else:
                yield from recurse_references(value)


def find_references(obj):
    """
    Find all ref prop names and their ID values from the given STIX object.
    This generator generates (ref_prop_name, ID) pairs for all reference
    properties.  For _refs properties (which are list-valued), a separate pair
    is generated for each element of the list; these pairs will contain the
    same property name and a different list element.

    :param obj: A STIX object with a "type" property.
    """
    for prop, value in obj.items():
        if prop.endswith("_ref"):
            yield prop, value

        elif prop.endswith("_refs"):
            for ref in value:
                yield prop, ref

        else:
            # Hack for observed-data: skip the inner SCO graph.  I don't
            # think we ever want to mix the two graphs!
            if obj["type"] != "observed-data" or prop != "objects":
                yield from recurse_references(value)


def recurse_references_assignable(obj):
    """
    Helper for find_references_assignable().  See that function for more
    information.  Can also be used as a more generic reference finder, which
    requires no particular structure (e.g. a "type" property) and has no
    special casing for observed-data/objects.

    :param obj: An object.  Can be any type, but values will only be produced
        from mappings.
    """
    if isinstance(obj, collections.abc.Mapping):
        for prop, value in obj.items():
            if prop.endswith("_ref"):
                yield obj, prop, value, prop

            elif prop.endswith("_refs"):
                for idx, ref_id in enumerate(value):
                    yield value, idx, ref_id, prop

            else:
                yield from recurse_references_assignable(value)


def find_references_assignable(obj):
    """
    Find all ref prop names and their ID values from the given object in a way
    that allows modification of the reference (i.e. assignment of a new ID to
    the reference property).  Generates 4-tuples

    (parent, key, ID, reference property name)

    where parent and key are such that the reference can be modified by
    assignment to the expression "parent[key]".  If the reference property is
    list-valued, parent will be the list and key will be an integer index;
    otherwise, parent will be a mapping and key will be a key from the mapping.
    ID is the value of parent[key] and is provided as a convenience so that
    callers can avoid doing an extra lookup to get it.  The reference property
    name will be the same as key, if key is string-valued (a _ref property
    name).  If parent is a list and key an integer, then the reference property
    name is the key which maps to that list (a _refs property name).

    For list-valued _refs properties, a tuple is generated for each element of
    the list: key and ID will change, but parent and the reference property
    name will be the same.

    :param obj: A STIX object with a "type" property.
    """
    for prop, value in obj.items():
        if prop.endswith("_ref"):
            yield obj, prop, value, prop

        elif prop.endswith("_refs"):
            for idx, ref_id in enumerate(value):
                yield value, idx, ref_id, prop

        else:
            # Hack for observed-data: skip the inner SCO graph.  I don't
            # think we ever want to mix the two graphs!
            if obj["type"] != "observed-data" or prop != "objects":
                yield from recurse_references_assignable(value)


def random_generatable_stix_type(
    object_generator, *required_types, stix_version="2.1"
):
    """
    Choose a STIX type at random which satisfies the given type constraints,
    and which the given object generator is able to generate.  See
    stix2.utils.is_stix_type() for more discussion on the type constraints.

    :param object_generator: An object generator
    :param required_types: Type constraints, as a sequence of STIX type strings
        and/or STIXTypeClass enum values.  If no types are given, it means no
        types are legal, so None will always be returned.
    :param stix_version: A STIX version as a string
    :return: A STIX type if one could be found which satisfies the given
        constraints; None if one could not be found
    """

    candidate_types = [
        type_ for type_ in object_generator.spec_names
        if stix2.utils.is_stix_type(
            type_, stix_version, *required_types
        )
    ]

    if candidate_types:
        stix_type = random.choice(candidate_types)
    else:
        stix_type = None

    return stix_type


def make_bundle(stix_objs, stix_version):
    """
    Creating a Bundle object of the given spec version, which contains the
    given STIX objects.

    :param stix_objs: The objects the bundle is to contain.  Must be a value
        accepted by the Bundle constructor, e.g. a single or list of objects.
    :param stix_version: A STIX version as a string
    :return: The Bundle object
    """

    bundle_class = stix2.registry.class_for_type("bundle", stix_version)
    bundle = bundle_class(stix_objs, allow_custom=True)

    return bundle

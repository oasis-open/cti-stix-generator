import collections
import collections.abc
import enum
import random
import stix2.utils

import stix2generator
import stix2generator.utils
import stix2generator.generation
import stix2generator.generation.object_generator


class InversePropertyConstraint:
    """
    Instances represent an "inverse" property constraint.  This type of
    constraint means that reference properties in each of two objects are
    "inverses" with respect to each other: if you set one to refer to a
    particular object, the inverse property of the other object must be set to
    refer to the first object.  They *must* refer to each others' objects.  An
    example of this is directory/content_refs and file/parent_directory_ref.
    This necessarily implies cycles in the graph.

    Constraint specification is simple: you just give two STIX object types and
    the property name from each which are inverses with respect to each other.
    This specification is also symmetric: (type1, A, type2, B) means the same
    as (type2, B, type1, A), where A and B are property names.

    Application of the constraint to a pair of objects however, may not be so
    simple.  The type and property names need not be distinct.  This can result
    in ambiguity in applying the constraint.  When type names are equal, an
    instance of the type may have both constraint properties.  Then, the
    constraint can apply in two different ways.  For example, consider the
    process SCO, which has child_refs and parent_ref properties, which are
    inverses:

        process1:
            child_refs=[2]
            parent_ref=2

        process2:
            child_refs=[3]
            parent_ref=1

    process1's child_refs refers to process2, so the constraint says process2's
    parent_ref must refer to process1.  It does, so the constraint holds in
    that case.  But process1's parent_ref refers to process2, and process2's
    child_refs does not refer to process1.  So the constraint does not hold in
    that case.  Both objects have both constraint properties, so the constraint
    effectively applies twice, and in each case independently, it may or may
    not hold.  So it's not sufficient to ask whether an arbitrary inverse
    property constraint holds between two arbitrary objects.  One must somehow
    express *how* to apply the constraint, in cases where there is ambiguity.

    So method signatures for this class include the ref_prop parameter for this
    purpose.  It expresses which constraint property in the first object
    (src_obj) you are interested in.  In results in asymmetry in the
    application of the constraint, despite the symmetry of the constraint
    itself.  For example, the holds() method is essentially checking for an
    inverse property cycle between two objects.  With respect to the
    (type1, A, type2, B) example above, invoking as holds(src_obj, A, dest_obj)
    means checking for the cycle:

        src_obj -> A -> dest_obj -> B -> src_obj

    whereas invoking as holds(src_obj, B, dest_obj) means checking for the
    cycle:

        src_obj -> B -> dest_obj -> A -> src_obj

    and those cycles are different (assuming A and B are different properties).
    """
    def __init__(self, object_type1, prop_name1, object_type2, prop_name2):
        """
        Initialize this constraint object.  The constraint is simply described
        with two object types and two bare property names.  So you can't
        distinguish same named properties in different locations inside of
        objects.  Only top-level properties are supported.  If constraints need
        to target non-top-level properties, more complexity will be necessary.

        :param object_type1: A STIX object type
        :param prop_name1: A reference property name from an object of type
            object_type1
        :param object_type2: Another STIX object type
        :param prop_name2: A reference property name from an object of type
            object_type2
        """
        self.__object_type1 = object_type1
        self.__prop_name1 = prop_name1
        self.__object_type2 = object_type2
        self.__prop_name2 = prop_name2

    def __repr__(self):
        return 'InversePropertyConstraint("{}", "{}", "{}", "{}")'.format(
            self.object_type1, self.prop_name1,
            self.object_type2, self.prop_name2
        )

    @property
    def object_type1(self):
        return self.__object_type1

    @property
    def prop_name1(self):
        return self.__prop_name1

    @property
    def object_type2(self):
        return self.__object_type2

    @property
    def prop_name2(self):
        return self.__prop_name2

    def is_applicable(self, src_obj, ref_prop, dest_obj):
        """
        Given a source/dest object and a ref property name, determine whether
        this constraint would constrain an inverse property of dest_obj.  To be
        applicable, the source object type and ref_prop must match with one of
        the type/property pairs of this constraint, dest_obj's type must
        match with the other type, it must possess the inverse property, and
        the source object must actually refer to dest_obj via ref_prop.
        dest_obj need not refer back to src_obj via the inverse property (if
        this constraint were actually enforced, it would be).

        :param src_obj: An object
        :param ref_prop: A property name
        :param dest_obj: Another object
        :return: True if this constraint matches the props/types of the objects
            and would constrain a property of dest_obj; False if not.
        """

        src_type = src_obj["type"]
        dest_type = dest_obj["type"]

        # check src/ref_prop matches with object/prop1,
        # dest matches object/prop2
        if self.object_type1 == src_type \
                and self.prop_name1 == ref_prop \
                and self.prop_name1 in src_obj \
                and self.object_type2 == dest_type \
                and self.prop_name2 in dest_obj:

            result = _refers_to(src_obj, self.prop_name1, dest_obj)

        # the reverse: check src/ref_prop matches with object/prop2
        elif self.object_type2 == src_type \
                and self.prop_name2 == ref_prop \
                and self.prop_name2 in src_obj \
                and self.object_type1 == dest_type\
                and self.prop_name1 in dest_obj:

            result = _refers_to(src_obj, self.prop_name2, dest_obj)

        else:
            result = False

        return result

    def is_applicable_types(self, src_type, ref_prop, dest_type):
        """
        Applicability check based only on types, not actual objects.  If an
        instance of src_type were linked to an instance of dest_type via the
        source object's ref_prop property, determine whether this constraint
        would constrain the dest instance (assuming it had the inverse
        property).

        :param src_type: An object type
        :param ref_prop: A property name
        :param dest_type: Another object type
        :return: True if an instance of dest_type would be constrained; False
            if not.
        """
        return (
            self.object_type1 == src_type
            and self.prop_name1 == ref_prop
            and self.object_type2 == dest_type
        ) or (
            self.object_type2 == src_type
            and self.prop_name2 == ref_prop
            and self.object_type1 == dest_type
        )

    def holds(self, src_obj, ref_prop, dest_obj):
        """
        Assuming applicability of this constraint (see is_applicable()), checks
        whether dest_obj refers back to src_obj via the inverse property (of
        ref_prop).

        :param src_obj: An object
        :param ref_prop: A property name
        :param dest_obj: Another object
        :return: True if the constraint holds; False if it does not
        """
        src_type = src_obj["type"]
        if self.object_type1 == src_type \
                and self.prop_name1 == ref_prop:
            result = _refers_to(dest_obj, self.prop_name2, src_obj)

        elif self.object_type2 == src_type \
                and self.prop_name2 == ref_prop:
            result = _refers_to(dest_obj, self.prop_name1, src_obj)

        else:
            result = False

        return result

    def enforce(self, src_obj, ref_prop, dest_obj):
        """
        Assuming applicability of this constraint (see is_applicable()),
        enforce this constraint on dest_obj.  This will force a property of
        dest_obj to refer to src_obj.  For a list-valued constraint property
        in dest_obj, an arbitrary element will be forced to src_obj's ID.

        :param src_obj: An object
        :param ref_prop: A property name
        :param dest_obj: Another object
        """

        if src_obj["type"] == self.object_type1 \
                and ref_prop == self.prop_name1:
            dest_prop_to_enforce = self.prop_name2
        else:
            dest_prop_to_enforce = self.prop_name1

        dest_prop_value = dest_obj[dest_prop_to_enforce]
        if isinstance(dest_prop_value, list):
            idx = random.randrange(len(dest_prop_value))
            dest_prop_value[idx] = src_obj["id"]

        else:
            dest_obj[dest_prop_to_enforce] = src_obj["id"]


_INVERSE_PROPERTIES = [
    InversePropertyConstraint(
        "network-traffic", "encapsulates_refs",
        "network-traffic", "encapsulated_by_ref"
    ),
    InversePropertyConstraint(
        "directory", "contains_refs", "file", "parent_directory_ref"
    ),
    InversePropertyConstraint(
        "process", "child_refs", "process", "parent_ref"
    )
]


class GraphType(enum.Enum):
    """
    Styles of graph:

    - TREE: No object "reuse", i.e. in-degree for all nodes is never greater
        than one.  Exceptions will occur for objects with fixed IDs, e.g. TLP
        marking definitions.
    - DAG: Directed acyclic graph: objects may be reused as long as no cycle is
        created.
    - RANDOM: Objects are randomly reused without regard to cycles.

    The acyclic graph topologies are still subject to inverse property cycles.
    So depending on how inverse property constraints are enforced, it may not
    be possible to have a truly acyclic graph.
    """
    TREE = 0
    DAG = 1
    RANDOM = 2


class InversePropertyConstraintEnforcement(enum.Enum):
    """
    An inverse property constraint is a constraint implied by two properties
    with an "inverse" relationship to each other.  (See the
    InversePropertyConstraint class.)  This enum determines how we should
    handle them.

    ENFORCE: Enforce them.  Where inverse properties occur, ensure they
        refer to each other's objects.  This means that acyclic graph
        topologies are not truly possible, because inverse properties will
        always result in a cycle.
    DELETE: Delete one of the properties.  This ensures inverse property
        cycles will not occur.  This is done naively, without regard to whether
        the property being deleted may have been required by spec.  So it could
        result in invalid objects, depending on how they were designed.
    IGNORE: Pretend there are no constraints.  This treats inverse properties
        as any other property.  This can result in nonsensical/contradictory
        semantics in the content.  E.g. directory1 contains file1, whose parent
        directory is directory2.  This means directory1 is declared to contain
        file1, but file1 claims to be in directory2.
    """
    ENFORCE = 0
    DELETE = 1
    IGNORE = 2


class Config(stix2generator.generation.Config):
    """
    Config settings for reference graph generation.

    - max_depth: about how many steps maximum from the "seed" object are we
        allowed to get.  This affects the maximum size of the graph.  It can't
        be strictly enforced, since one can't generally guarantee that a
        generated object will have no reference properties.
    - graph_type: what style of graph to create.  See the GraphType enum.
    - probability_reuse: when creating an object graph, in those situations
        where we can choose to reuse an already-created object, this determines
        how likely we are to choose to reuse.
    - inverse_property_constraints: how to handle inverse property constraints.
        See the InversePropertyConstraintEnforcement enum.
    """

    _DEFAULTS = {
        "max_depth": 3,
        "graph_type": GraphType.DAG,
        "probability_reuse": 0.5,
        "inverse_property_constraints":
            InversePropertyConstraintEnforcement.ENFORCE
    }


def _refers_to(src_obj, ref_prop, dest_obj):
    """
    Determine whether src_obj refers to dest_obj via reference property
    ref_prop.

    :param src_obj: A STIX object
    :param ref_prop: A reference property
    :param dest_obj: Another STIX object
    :return:
    """
    if ref_prop in src_obj:
        prop_value = src_obj[ref_prop]
        if isinstance(prop_value, list):
            result = dest_obj["id"] in prop_value
        else:
            result = prop_value == dest_obj["id"]

    else:
        result = False

    return result


def _is_reachable(src_id, dest_id, by_id, visited_ids=None):
    """
    Determine whether dest_id is reachable from src_id, following reference
    properties.

    :param src_id: A source object ID
    :param dest_id: A destination object ID
    :param by_id: The graph, as a mapping from ID to object
    :param visited_ids: A set which tracks visited IDs to avoid infinitely
        following cycles in the graph.  If None, a new set is automatically
        created and used.
    :return: True if dest_id is reachable from src_id; False if not
    """

    if src_id == dest_id:
        result = True

    elif src_id not in by_id:
        # Don't assume a "completed" ref graph, where every ref corresponds
        # to an existing graph node.  Be robust in case the graph is in a state
        # of partial construction and there are still some dangling references.
        result = False

    else:
        if visited_ids is None:
            visited_ids = set()

        if src_id in visited_ids:
            result = False
        else:
            visited_ids.add(src_id)

            src_obj = by_id[src_id]
            for _, ref_id in stix2generator.utils.find_references(src_obj):
                if _is_reachable(ref_id, dest_id, by_id, visited_ids):
                    result = True
                    break

            else:
                result = False

    return result


def _find_property_constraints(src_obj, ref_prop, dest_obj):
    """
    Generate InversePropertyConstraint instances applicable to src_obj and
    dest_obj, specifically with respect to the ref_prop property of src_obj.

    :param src_obj: An object
    :param ref_prop: A property name
    :param dest_obj: Another object
    """
    for constraint in _INVERSE_PROPERTIES:
        if constraint.is_applicable(src_obj, ref_prop, dest_obj):
            yield constraint


def _would_be_constrained(src_type, ref_prop, dest_type):
    """
    Determines whether if an object of type src_type hypothetically
    referred to an object of type dest_type via reference property
    ref_prop, would an inverse property constraint apply to the destination
    object and require it to be modified.  This is important for object reuse:
    if we want to reuse an object which has already had all its properties
    suitably set, we mustn't overwrite any of them to enforce an inverse
    property constraint.  Therefore, we can't reuse any object we'd have to
    apply a constraint to.

    I think this should be the case even if an instance of dest_type doesn't
    have the inverse property.  Graph semantics could still be wrong.  E.g.
    consider two directories who both say they contain the same file, where the
    file has no parent_directory_ref.  It doesn't matter whether the inverse
    property (parent_directory_ref) is present or not; it still doesn't make
    sense.

    :param src_type: A source object type
    :param ref_prop: A reference property name defined for src_obj_type
    :param dest_type: A destination object type
    :return: True if we'd have to apply a constraint to the destination object;
        False if not.
    """

    result = any(
        constraint.is_applicable_types(src_type, ref_prop, dest_type)
        for constraint in _INVERSE_PROPERTIES
    )

    return result


def _apply_constraints(src_obj, ref_prop, dest_obj):
    """
    Assuming src_obj refers to dest_obj via reference property ref_prop, apply
    any required inverse property constraints to dest_obj.

    :param src_obj: A source object
    :param ref_prop: A reference property name from src_obj
    :param dest_obj: A destination object to apply constraints to
    """
    constraints = _find_property_constraints(src_obj, ref_prop, dest_obj)
    for constraint in constraints:
        constraint.enforce(src_obj, ref_prop, dest_obj)


def _delete_inverse_properties(src_obj, ref_prop, dest_obj):
    """
    Assuming src_obj refers to dest_obj via reference property ref_prop,
    remove all inverse properties from dest_obj we would have to constrain, in
    order to avoid needing to apply any constraints.  This ensures there are no
    "back reference" properties pointing from dest_obj back to src_obj.

    :param src_obj: A source object
    :param ref_prop: A reference property name from src_obj
    :param dest_obj: A destination object to remove inverse properties from
    """
    constraints = _find_property_constraints(src_obj, ref_prop, dest_obj)

    for constraint in constraints:
        # the prop to delete is the inverse of ref_prop.
        if constraint.prop_name1 == ref_prop:
            prop_to_delete = constraint.prop_name2
        else:
            prop_to_delete = constraint.prop_name1

        dest_obj.pop(prop_to_delete, None)


class ReferenceGraphGenerator:
    """
    Instances of this class can generate object graphs such that the nodes
    are objects and edges correspond to reference properties of those
    objects.  These graphs do not use SROs.  Generation is designed to prevent
    any dangling references in the resulting graph.
    """

    def __init__(
        self, object_generator, config=None, stix_version="2.1"
    ):
        """
        Initialize this reference graph generator.

        :param object_generator: An instance of the built-in object generator
            to use for generating the objects.
        :param config: Config settings for the generator.
        """

        self.__config = config or Config()
        self.__object_generator = object_generator
        self.__stix_version = stix_version

        # A big problem that must be solved is how to stop the graph from
        # growing too large.  We can't simply stop generating objects, because
        # there must be no dangling references.  We also can't just keep
        # generating objects because the graph can balloon to enormous size.
        # My solution is to take advantage of the reference minimization
        # capability of the built-in object generator.  If we minimize
        # references, we minimize the number of new objects which need to be
        # generated, and that acts to put the brakes on growth.  We can't
        # minimize references all the time, because then the graph wouldn't
        # be able to grow much.  So we need two generators: one which generates
        # objects "normally" and is used to grow the graph, and one which
        # minimizes references, which is used to halt growth when we need it to
        # stop.

        halt_generator_config_dict = vars(object_generator.config).copy()
        halt_generator_config_dict["minimize_ref_properties"] = True
        halt_generator_config = stix2generator.generation.object_generator\
            .Config(
                **halt_generator_config_dict
            )
        self.__halt_generator = stix2generator.create_object_generator(
            halt_generator_config
        )

    @property
    def config(self):
        return self.__config

    def __random_generatable_seed_type(self, *constraints):
        """
        Pick a random seed type for a reference graph.

        :return: A random generatable seed STIX type
        :raises stix2generator.exceptions.GeneratableSTIXTypeNotFoundError: if
            a satisfying generatable STIX type could not be found
        """

        stix_type = stix2generator.utils.random_generatable_stix_type(
            self.__object_generator,
            *constraints,
            stix_version=self.__stix_version
        )

        if not stix_type:
            raise stix2generator.exceptions.GeneratableSTIXTypeNotFoundError(
                constraints, self.__stix_version
            )

        return stix_type

    def __augment_graph(self, object_, by_id, by_type, depth):
        """
        Build the graph out from the given object: find its reference
        properties and either create new objects for those properties to refer
        to, or choose other existing objects for them to refer to.

        :param object_: The graph object we are building out from
        :param by_id: The current graph, as a mapping from ID to object
        :param by_type: Another data structure containing the current graph
            nodes, as a mapping from STIX type name to a list of IDs of objects
            of that type.  This enables efficient lookup by type.
        :param depth: How many steps from the initial "seed" node the given
            object is.  Determines whether we need to stop graph growth.
        """

        if depth < self.config.max_depth:
            gen = self.__object_generator
        else:
            gen = self.__halt_generator

        for parent, key, ref_id, ref_prop \
                in stix2generator.utils.find_references_assignable(object_):

            # Constrained reference properties will refer to objects already
            # in the graph.  We must be careful not to disturb those.
            if ref_id in by_id:
                continue

            ref_type = stix2.utils.get_type_from_id(ref_id)
            new_object = None

            if self.config.graph_type is GraphType.TREE:
                # always generate a new object.
                new_object = gen.generate(ref_type)

            elif self.config.graph_type is GraphType.DAG:
                # Allow reuse if it doesn't create a cycle and it would not
                # require overwriting a property of the reused object due to
                # inverse property constraint enforcement.
                if (ref_type in by_type and
                        random.random() < self.config.probability_reuse and
                        (self.config.inverse_property_constraints is
                         InversePropertyConstraintEnforcement.IGNORE
                         or not _would_be_constrained(
                             object_["type"], ref_prop, ref_type
                         ))):
                    # Need to choose a random object which doesn't cause a
                    # cycle.  sample() here produces a new shuffled list,
                    # rather than shuffling in-place.  Shuffling means we can
                    # try each ID once, while at the same time not having a
                    # preference for IDs earlier in the original list.  The
                    # choice ought to be more random.
                    ids = by_type[ref_type]
                    shuffled_ids = random.sample(ids, k=len(ids))
                    for id_ in shuffled_ids:
                        if not _is_reachable(id_, object_["id"], by_id):
                            parent[key] = id_
                            break

                    else:
                        # All existing objects would create a cycle.  No
                        # choice but to create a new object.
                        new_object = gen.generate(ref_type)

                else:
                    new_object = gen.generate(ref_type)

            elif self.config.graph_type is GraphType.RANDOM:
                # Reuse randomly, not caring about cycles.
                if (ref_type in by_type and
                        random.random() < self.config.probability_reuse and
                        (self.config.inverse_property_constraints is
                         InversePropertyConstraintEnforcement.IGNORE
                         or not _would_be_constrained(
                            object_["type"], ref_prop, ref_type
                        ))):
                    id_ = random.choice(by_type[ref_type])
                    parent[key] = id_

                else:
                    new_object = gen.generate(ref_type)

            if new_object:

                # Replace the ref in the source obj with the dest object's ID,
                # rather than the other way around.  This is necessary since
                # some objects (e.g. certain marking definitions) are generated
                # with specific IDs they *must* use.  We mustn't replace them.
                new_object_id = new_object["id"]
                parent[key] = new_object_id

                if self.config.inverse_property_constraints is \
                        InversePropertyConstraintEnforcement.ENFORCE:
                    _apply_constraints(object_, ref_prop, new_object)
                elif self.config.inverse_property_constraints is \
                        InversePropertyConstraintEnforcement.DELETE:
                    _delete_inverse_properties(
                        object_, ref_prop, new_object
                    )
                # else IGNORE: leave new_object as-is

                by_id[new_object_id] = new_object
                by_type.setdefault(ref_type, []).append(new_object_id)

                self.__augment_graph(new_object, by_id, by_type, depth+1)

    def generate(self, seed_type=None, preexisting_objects=None):
        """
        Generate a reference graph seeded with an object of the given type.
        For graph types which allow reuse, preexisting_objects provides a way
        to reuse pre-existing objects.  This can be helpful when larger amounts
        of graph content is built up incrementally, so that new regions of
        content can connect with existing regions, instead of each invocation
        producing its own disconnected "island" of content.

        :param seed_type: A STIX type, STIXTypeClass enum, or None.  Generation
            is done by "building out" from a seed object.  This parameter
            determines the type of the seed object.  If None, a STIX SDO or SCO
            is chosen at random.
        :param preexisting_objects: The pre-existing STIX content, as either a
            list of objects or mapping from ID to object.
        :return: A 2-tuple including (1) The ID of the object which was created
            as the seed, and (2) the generated content, as a mapping from ID to
            object.  If preexisting_objects was given as a map, the same map is
            returned, updated with the new content.  Otherwise, a new map is
            created and returned.  It will contain all of the data from
            preexisting_objects plus the new content.
        """
        if not seed_type:
            seed_type = self.__random_generatable_seed_type(
                stix2generator.utils.STIXTypeClass.SDO,
                stix2generator.utils.STIXTypeClass.SCO
            )
        else:
            # Might seem kinda silly if seed_type is directly given as a string,
            # but this ensures that the given seed type is actually generatable
            # with our object generator.
            seed_type = self.__random_generatable_seed_type(seed_type)

        # Pre-populate our data structures, if we were given pre-existing
        # objects.
        if preexisting_objects is not None:
            if isinstance(preexisting_objects, collections.abc.Mapping):
                by_id = preexisting_objects
            else:
                by_id = {
                    obj["id"]: obj
                    for obj in preexisting_objects
                }
        else:
            by_id = {}

        # Wrapping the base preexisting objects map this way allows us to
        # easily distinguish new objects we create from old objects we were
        # given.  At the end, we only want to parse the new objects.
        by_id = collections.ChainMap(by_id).new_child()

        # For fast lookup of all generated objects of a particular type.  Maps
        # STIX type name to a list of object IDs of that type.
        by_type = {}

        for id_, obj in by_id.items():
            by_type.setdefault(obj["type"], []).append(id_)

        if self.config.max_depth == 0:
            gen = self.__halt_generator
        else:
            gen = self.__object_generator

        seed_object = gen.generate(seed_type)
        seed_id = seed_object["id"]

        by_type.setdefault(seed_type, []).append(seed_id)
        by_id[seed_id] = seed_object

        self.__augment_graph(seed_object, by_id, by_type, 0)

        # Parse the new objects we created and incorporate them into the base
        # graph.
        new_objects = by_id.maps[0]
        by_id = by_id.maps[1]
        for new_id, new_obj_dict in new_objects.items():
            by_id[new_id] = stix2.parse(
                new_obj_dict, version=self.__stix_version, allow_custom=True
            )

        return seed_id, by_id

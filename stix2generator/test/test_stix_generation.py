import itertools

import pytest
import stix2.base
import stix2.utils

import stix2generator
import stix2generator.exceptions
import stix2generator.generation.object_generator
import stix2generator.generation.stix_generator
import stix2generator.test.utils
import stix2generator.utils


@pytest.mark.parametrize(
    "seed_type", [
        "identity",
        stix2.utils.STIXTypeClass.SDO,
        stix2.utils.STIXTypeClass.SCO,
        stix2.utils.STIXTypeClass.SRO
    ]
)
def test_seeds(num_trials, seed_type, stix21_generator):
    for _ in range(num_trials):
        graph = stix21_generator.generate(seed_type)

        # Ensure the graph has at least one object of type seed_type.
        assert any(
            stix2.utils.is_stix_type(
                obj, "2.1", seed_type
            )
            for obj in graph.values()
        )


def test_bad_seed(stix21_generator):
    with pytest.raises(stix2generator.exceptions.GeneratableSTIXTypeNotFoundError):
        stix21_generator.generate("foo")


def _count_relationships(graph):
    """
    Counts the number of relationships (plain and sighting) in the graph.
    """
    count = sum(
        1 if stix2.utils.is_sro(obj, "2.1") else 0
        for obj in graph.values()
    )

    return count


def test_relationship_count(num_trials):
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        min_relationships=2,
        max_relationships=5
    )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config
    )

    for _ in range(num_trials):
        graph = stix_gen.generate()
        rel_count = _count_relationships(graph)
        assert 2 <= rel_count <= 5


def test_complete_ref_properties_true(num_trials):
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        complete_ref_properties=True
    )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config
    )

    for _ in range(num_trials):
        graph = stix_gen.generate()
        assert not stix2generator.test.utils.has_dangling_references(graph)


def test_complete_ref_properties_false(num_trials):
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        complete_ref_properties=False
    )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config
    )

    for _ in range(num_trials):
        graph = stix_gen.generate()

        # I think that if complete_ref_properties is False, non-relationship
        # ref properties would always have to be dangling.  If there are no
        # non-relationship ref properties, none would be dangling, because it
        # would be an error for a relationship to refer to a non-existent
        # object.
        for id_, obj in graph.items():

            if not stix2.utils.is_sro(obj, "2.1"):
                first_ref = next(
                    stix2generator.utils.find_references(obj), None
                )
                has_non_relationship_ref_props = first_ref is not None
                if has_non_relationship_ref_props:
                    break
        else:
            has_non_relationship_ref_props = False

        if has_non_relationship_ref_props:
            assert stix2generator.test.utils.has_dangling_references(graph)
        else:
            assert not stix2generator.test.utils.has_dangling_references(graph)


def test_probability_sighting(num_trials):
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        probability_sighting=0
    )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config
    )

    for _ in range(num_trials):
        graph = stix_gen.generate()
        has_sighting = any(
            obj["type"] == "sighting"
            for obj in graph.values()
        )

        assert not has_sighting

    # can't test that probability_sighting=1 results in *only*
    # sightings, because STIX graph generation can't guarantee that.


def test_connectedness(num_trials, stix21_generator):
    for _ in range(num_trials):
        graph = stix21_generator.generate()
        assert stix2generator.test.utils.is_connected(graph)


class _FilterFirst:
    """
    Instances act as a predicate which is used to filter out only the first
    occurrence of some value.
    """
    def __init__(self, filter_value):
        """
        Initialize this predicate object.

        :param filter_value: The value whose first occurrence this predicate
            should filter out.
        """
        self.filter_value = filter_value
        self.found = False

    def __call__(self, value):
        """
        Check whether the given value should pass this filter.

        :param value: A value
        :return: True if the value passes this filter; False if not
        """
        passes = True
        if value == self.filter_value and not self.found:
            self.found = True
            passes = False

        return passes


def _sro_relates(sro, id_):
    """
    Determine whether the given SRO relates an object with the given ID to
    any other object.

    :param sro: An SRO
    :param id_: A STIX ID
    :return: True if SRO relates id_ to something; False if not
    """
    sro_type = sro["type"]
    if sro_type == "relationship":
        relates = id_ in (sro["source_ref"], sro["target_ref"])

    else:
        # sightings
        relates = id_ == sro["sighting_of_ref"] \
            or id_ in sro.get("observed_data_refs", []) \
            or id_ in sro.get("where_sighted_refs", [])

    return relates


def _get_sro_other_ends(sro, this_end_id):
    """
    Given an SRO and and the ID of an object it relates, find all the IDs
    of other objects it relates the given ID to.  This is a generator which
    yields STIX IDs.

    :param sro: An SRO
    :param this_end_id: A STIX ID which the SRO relates to other things
    """

    sro_type = sro["type"]

    if sro_type == "relationship":
        other_end_id = sro["target_ref"] \
            if this_end_id == sro["source_ref"] \
            else sro["source_ref"]

        yield other_end_id

    else:
        # sightings
        observed_data_refs = sro.get("observed_data_refs")
        where_sighted_refs = sro.get("where_sighted_refs")
        sighting_of_refs = (sro["sighting_of_ref"],)  # always one of these

        # We assume this_end_id exists in some relevant ref property for
        # the sighting: that's one "end" of it.  All other ref IDs are the
        # other "ends".  In fact, this_end_id could occur multiple times.
        # We don't care where it occurs, but one of those is this end, and
        # all others are other ends.  The net result is that we want all ref
        # IDs from the relevant ref properties, minus a single ID matching
        # this_end_id.  The following simply filters out the first occurrence
        # as "this end".

        # chain together all of the ref IDs in the sighting
        all_refs = itertools.chain.from_iterable(
            seq for seq in (
                observed_data_refs, where_sighted_refs, sighting_of_refs
            ) if seq
        )

        # filter the first occurrence of this_end_id from the chain
        filter_first_pred = _FilterFirst(this_end_id)
        filtered_all_refs = (
            id_ for id_ in all_refs if filter_first_pred(id_)
        )

        yield from filtered_all_refs


def _sro_cycle_undirected_dfs(
    graph, curr_id, visited_ids=None, search_stack=None
):
    """
    Do a depth-first-search starting from curr_id in the given graph, and look
    for cycles.  This treats SROs as edges, and SROs' "endpoints" as graph
    nodes.  SRO directionality is ignored (sightings don't have a "direction"
    anyway).

    :param graph: The STIX graph as a mapping from ID to object
    :param curr_id: A start object ID for the search.  Must be an SDO or SCO
        ID (a type usable as an SRO endpoint).
    :param visited_ids: A set of IDs of objects we've already seen.  Prevents
        re-traversing the same graph regions multiple times
    :param search_stack: A search stack which builds up a path from the
        start node to other nodes.  This is used to detect the cycles.
    :return: True if a cycle is detected; False if not
    """
    if visited_ids is None:
        visited_ids = set()

    if search_stack is None:
        search_stack = []

    if curr_id in search_stack:
        result = True

    elif curr_id in visited_ids:
        result = False

    elif curr_id not in graph:
        # dangling reference
        result = False

    else:
        visited_ids.add(curr_id)
        search_stack.append(curr_id)

        for id_, obj in graph.items():
            # Need to add the SROs to the stack too, because we don't want to
            # reuse them in a cycle.  Cycles require distinct objects *and*
            # distinct SROs.
            if stix2.utils.is_sro(obj, "2.1") \
                    and id_ not in search_stack \
                    and _sro_relates(obj, curr_id):

                search_stack.append(id_)

                for other_end_id in _get_sro_other_ends(obj, curr_id):
                    result = _sro_cycle_undirected_dfs(
                        graph, other_end_id, visited_ids, search_stack
                    )

                    if result:
                        break

                else:
                    search_stack.pop()
                    continue

                search_stack.pop()
                break
        else:
            result = False

        search_stack.pop()

    return result


def _has_sro_cycle_undirected(graph):
    """
    Determine whether the given graph has an SRO-based cycle.  SRO
    directionality is ignored (sightings don't have a "direction" anyway).

    :param graph: The STIX graph as a mapping from ID to object
    :return: True if a cycle is detected; False if not
    """
    # Need to find a start node, i.e. a SRO-connectable object in the graph.
    sro_connectable_ids = (
        id_ for id_, obj in graph.items() if stix2.utils.is_stix_type(
            obj,
            "2.1",
            stix2.utils.STIXTypeClass.SDO,
            stix2.utils.STIXTypeClass.SCO,
        )
    )

    first_id = next(sro_connectable_ids, None)

    # Should not happen: it would mean the graph is empty or contains no
    # "normal" graph nodes (SDO/SCOs)!
    assert first_id is not None

    result = _sro_cycle_undirected_dfs(graph, first_id)
    return result


def test_probability_reuse(num_trials):
    # There shouldn't be any "cycles" if probability_reuse=0, since every
    # SRO addition results in all new objects.  I don't think there's any
    # invariant we can test when probability_reuse=1...
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        probability_reuse=0
    )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config,
        stix_version="2.1"
    )

    for _ in range(num_trials):
        graph = stix_gen.generate()
        assert not _has_sro_cycle_undirected(graph)


@pytest.mark.parametrize(
    "seed_type", [
        "marking-definition",
        "relationship",
        "sighting"
    ]
)
def test_non_sro_connectable(num_trials, stix21_generator, seed_type):
    for _ in range(num_trials):
        stix21_generator.generate(seed_type)


def _observable_container_has_dangling_references(observable_container):
    """
    Check all reference properties of all SCOs in the container, and determine
    whether they reference objects which are also in the container.

    :param graph: A STIX graph as a mapping from ID to object
    :return: True if any references are dangling; False if not
    """
    # This is almost a copy-paste of
    # stix2generator.test.utils.has_dangling_references(), but changed to work
    # on an observable-container, which is not a full STIX object.
    for obj in observable_container.values():
        for _, obj_id in stix2generator.utils.recurse_references(obj):
            if obj_id not in observable_container:
                result = True
                break
        else:
            continue

        break
    else:
        result = False

    return result


def test_observed_data_observable_container(num_trials):
    """
    Because of observed-data special-casing which occurs in the codebase,
    this test is intended to ensure that SDO in particular isn't getting messed
    up.
    """
    # To induce observed-data SDOs to have an "objects" property (as opposed to
    # the new "object_refs" property), configure the object generator to
    # minimize properties.  This will inhibit "object_refs" (since that's a ref
    # property) and force "objects".
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    stix_gen = stix2generator.create_stix_generator(
        object_generator_config=obj_gen_config
    )
    for _ in range(num_trials):
        graph = stix_gen.generate("observed-data")
        for id_, obj in graph.items():
            if obj["type"] == "observed-data":
                observable_container = obj["objects"]

                assert not _observable_container_has_dangling_references(
                    observable_container
                )


def test_preexisting_objects(stix21_generator, num_trials):
    for _ in range(num_trials):
        graph1 = stix21_generator.generate()

        graph2 = stix21_generator.generate(preexisting_objects=graph1)

        # ensure graph2 absorbed graph1
        assert graph1.keys() <= graph2.keys()

        # ensure all objects got parsed ok
        assert all(
            isinstance(obj, stix2.base._STIXBase)
            for obj in graph2.values()
        )


def test_stix2_parsing(stix21_generator, num_trials):
    identity = {
        "id": "identity--74fa9f1b-897e-40dc-8f1c-d2f531c956bb",
        "type": "identity",
        "spec_version": "2.1"
        # Omit the required "name" property.
        # Should be ok since the property is not used by any generators,
        # and we don't expect this dict to be parsed and produce any
        # validation errors.
    }

    for _ in range(num_trials):
        graph1 = {
            identity["id"]: identity
        }

        graph2 = stix21_generator.generate(preexisting_objects=graph1)

        # ensure graph2 absorbed graph1
        assert graph1.keys() <= graph2.keys()

        # ensure our preexisting identity is still a dict, but other objects
        # were parsed.
        for id_, obj in graph2.items():
            if id_ == identity["id"]:
                assert isinstance(obj, dict)
            else:
                assert isinstance(obj, stix2.base._STIXBase)


def test_not_stix2_parsing(num_trials):
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        parse=False
    )

    ref_graph_config = stix2generator.generation.reference_graph_generator \
        .Config(
            parse=False
        )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config,
        ref_graph_generator_config=ref_graph_config,
        stix_version="2.1"
    )

    identity = stix2.v21.Identity(
        name="Alice"
    )

    for _ in range(num_trials):
        graph1 = {
            identity.id: identity
        }

        graph2 = stix_gen.generate(preexisting_objects=graph1)

        # ensure graph2 absorbed graph1
        assert graph1.keys() <= graph2.keys()

        # Ensure the only parsed object is our original identity.
        for id_, obj in graph2.items():
            if id_ == identity.id:
                assert isinstance(obj, stix2.v21.Identity)

            else:
                assert isinstance(obj, dict)


def test_mixed_parse1(num_trials):

    # Test mixed parse settings:

    # STIXGenerator: parse=False
    # ReferenceGraphGenerator: parse=True
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        parse=False
    )

    ref_graph_config = stix2generator.generation.reference_graph_generator \
        .Config(
            parse=True
        )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config,
        ref_graph_generator_config=ref_graph_config,
        stix_version="2.1"
    )

    for _ in range(num_trials):
        # Nothing much to check here; some objects may be parsed, some may be
        # plain dicts.  Just make sure there are no errors?
        stix_gen.generate()


def test_mixed_parse2(num_trials):

    # Test mixed parse settings:

    # STIXGenerator: parse=True
    # ReferenceGraphGenerator: parse=False
    stix_gen_config = stix2generator.generation.stix_generator.Config(
        parse=True
    )

    ref_graph_config = stix2generator.generation.reference_graph_generator \
        .Config(
            parse=False
        )

    stix_gen = stix2generator.create_stix_generator(
        stix_generator_config=stix_gen_config,
        ref_graph_generator_config=ref_graph_config,
        stix_version="2.1"
    )

    for _ in range(num_trials):
        graph = stix_gen.generate()

        # Now we have something to test.  All objects should be parsed.
        for obj in graph.values():
            assert isinstance(obj, stix2.base._STIXBase)

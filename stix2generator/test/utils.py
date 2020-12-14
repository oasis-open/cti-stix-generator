"""
Utilities useful for unit tests.
"""
import stix2generator.utils


def has_dangling_references(graph):
    """
    Check all reference properties of all objects in the graph, and determine
    whether they reference objects which are also in the graph.

    :param graph: A STIX graph as a mapping from ID to object
    :return: True if any references are dangling; False if not
    """
    for obj in graph.values():
        for _, obj_id in stix2generator.utils.find_references(obj):
            if obj_id not in graph:
                result = True
                break
        else:
            continue

        break
    else:
        result = False

    return result


def _ref_dfs(graph, curr_id, new_ids, visited_ids):
    """
    Do a depth-first-search via reference properties starting at node
    curr_id, and add any IDs encountered which are not in visited_ids, to
    new_ids.  Note that dangling references, i.e. references to non-existent
    objects are not added to new_ids.

    This allows you to see a kind of "delta": given an ID, those IDs it makes
    newly reachable relative to the set of IDs you've already seen.

    :param graph: A STIX graph as a mapping from ID to object
    :param curr_id: The ID of a start node for DFS
    :param new_ids: A set which collects "new" IDs encountered, i.e. those
        encountered which are not in visited_ids.  This includes curr_id
        itself, if it has not already been seen.
    :param visited_ids: A set of previously found IDs.  This set is not
        modified.
    """

    if curr_id in new_ids or curr_id in visited_ids:
        return

    curr_node = graph.get(curr_id)
    if curr_node is None:
        # a dangling reference
        return

    new_ids.add(curr_id)

    for _, id_ in stix2generator.utils.find_references(curr_node):
        _ref_dfs(graph, id_, new_ids, visited_ids)


def _find_new_referring_ids(graph, new_ids, visited_ids):
    """
    Find IDs of objects which refer to an object with an ID in new_ids, which
    have not themselves already been seen.

    This allows you to take a sort of "upstream" step when traversing a STIX
    graph.  If "downstream" means following a ref property to its referent,
    this function allows you to follow a referent backward to its referring
    objects.

    The "seen" objects are those with IDs in either new_ids or visited_ids.
    new_ids is a "delta", i.e. a newly discovered set of connected IDs, which
    comes from _ref_dfs().  So this and that function work together.

    :param graph: A STIX graph as a mapping from ID to object
    :param new_ids: A set of STIX IDs
    :param visited_ids: Another set of STIX IDs
    :return: A set of IDs of objects which refer to objects with IDs in new_ids
    """
    referring_ids = set()
    for id_, obj in graph.items():
        if id_ not in new_ids and id_ not in visited_ids:
            for _, ref_id in stix2generator.utils.find_references(obj):
                if ref_id in new_ids:
                    referring_ids.add(id_)

    return referring_ids


def is_connected(graph):
    """
    Determine whether the graph is connected, i.e. whether there is any
    partitioning such that one cannot reach one partition from another by
    following references (forward or backward).  Because SROs also actually
    connect things via their reference properties, this works as a
    connectedness check for both reference graphs (as built by the reference
    graph generator) and SRO-based graphs.
    """

    # Note that because _ref_dfs() ignores dangling references, that can cause
    # a pattern like the following to result in a detected disconnection:
    #
    # {
    #   "A": {"some_ref": "C"},
    #   "B": {"some_ref": "C"}
    # }
    #
    # A will not be detected as connecting to B because C does not exist.
    # Should it?  Does it make sense to say they connect through an object
    # which doesn't exist, even though the IDs are equal?  But I think this is
    # very unlikely to happen.  That suggests maybe it should cause failure so
    # we can tell whether something we don't expect to happen, actually happens.

    curr_id = next(iter(graph), None)

    if curr_id:
        visited_ids = set()
        new_ids = set()
        _ref_dfs(graph, curr_id, new_ids, visited_ids)
        while new_ids:
            referring_ids = _find_new_referring_ids(
                graph, new_ids, visited_ids
            )

            visited_ids |= new_ids
            new_ids.clear()

            for id_ in referring_ids:
                _ref_dfs(graph, id_, new_ids, visited_ids)

        disconnected_ids = graph.keys() - visited_ids
        result = not bool(disconnected_ids)

    else:
        # If no nodes, I guess it's considered "connected"...?
        # Shouldn't happen though.
        result = True

    return result

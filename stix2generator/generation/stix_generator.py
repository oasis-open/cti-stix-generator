import collections
import collections.abc
import itertools
import random
import stix2.utils

import stix2generator.exceptions
import stix2generator.generation
import stix2generator.generation.reference_graph_generator
import stix2generator.generation.relationships
import stix2generator.utils


class Config(stix2generator.generation.Config):
    """
    STIX generator config settings.

    min/max_relationships: Limits on the number of SROs created.  This
        influences (but does not solely determine) the size of the resulting
        graph.

    probability_reuse: One endpoint of every SRO connects to existing content,
        to avoid partitioning the graph.  This setting determines how likely
        the other endpoint(s) are to refer to existing content.

    probability_sighting: When each SRO is added, with this probability, a
        sighting will be attempted instead of a "plain" relationship.  A plain
        relationship is still used as a fallback if a sighting cannot be
        created.

    complete_ref_properties: When an object is created, whether or not to
        leave its reference properties dangling.  Applies only to
        non-SRO-endpoint reference properties.
    """
    _DEFAULTS = {
        "min_relationships": 3,
        "max_relationships": 6,
        "probability_reuse": 0.5,
        "probability_sighting": 0.2,
        "complete_ref_properties": True
    }


def _random_id_of_types(by_type, *types, stix_version="2.1"):
    """
    Choose a random ID of one of the given types, from the by_type mapping.

    :param by_type: A mapping from STIX type to a list of STIX IDs of that type
    :param types: The STIX types of interest.  If no types are given, it means
        no types are legal, so None will always be returned.
    :param stix_version: The STIX version used to evaluate constraints
    :return: A STIX ID of one of the given types, or None if by_types is empty
        or does not contain any IDs of any of the required types.
    """

    # This is a bit more complicated, but produces a uniform distribution over
    # the IDs.  A simpler way would be to choose a random type first, and then
    # a random ID of the chosen type, but that would not result in a uniform
    # distribution over IDs.

    num_ids = sum(
        len(ids)
        for type_, ids in by_type.items()
        if stix2generator.utils.is_stix_type(
            type_, *types, stix_version=stix_version
        )
    )

    if num_ids == 0:
        id_ = None

    else:
        id_iter = itertools.chain.from_iterable(
            ids
            for type_, ids in by_type.items()
            if stix2generator.utils.is_stix_type(
                type_, *types, stix_version=stix_version
            )
        )

        id_ = stix2generator.utils.rand_iterable(
            id_iter, num_ids
        )

    return id_


def _is_sro_connectable(obj_or_type, stix_version):
    """
    Checks whether the given STIX type, or the type of the given STIX object
    is "connectable" via (plain, non-sighting) SRO.  I.e. can it appear as
    the source or target ref of an SRO.

    :param obj_or_type: A mapping with a "type" property, or a STIX type
        as a string
    :param stix_version: A STIX version as a string
    :return: True if the type is connectable via SRO; False if not
    """
    return stix2generator.utils.is_stix_type(
        obj_or_type,
        stix2generator.utils.STIXTypeClass.SDO,
        stix2generator.utils.STIXTypeClass.SCO,
        stix_version=stix_version
    )


def _random_sro_connectable_id(by_type, stix_version):
    """
    Choose a random ID of an SRO-connectable type (see _is_sro_connectable())
    from the by_type map.

    :param by_type: A map from STIX type to a list of IDs of STIX objects in
        the current graph of that type
    :param stix_version: A STIX version as a string
    :return: An SRO-connectable STIX ID
    """
    return _random_id_of_types(
        by_type,
        stix2generator.utils.STIXTypeClass.SDO,
        stix2generator.utils.STIXTypeClass.SCO,
        stix_version=stix_version
    )


class STIXGenerator:
    """
    Instances generate STIX content: STIX objects related by SROs and
    embedded relationships.
    """

    def __init__(
        self, object_generator, ref_graph_generator=None, config=None,
        stix_version="2.1"
    ):
        """
        Initialize this STIX generator.

        :param object_generator: An instance of the built-in object generator
            to use for generating the objects.
        :param ref_graph_generator: A reference graph generator used if
            dangling references must be avoided.  If None, automatically create
            one with default config settings.
        :param config: A Config object with settings for this generator.
        :param stix_version: A STIX version, as a string.
        """
        self.__object_generator = object_generator
        self.__ref_graph_generator = \
            ref_graph_generator \
            or stix2generator.generation.reference_graph_generator\
            .ReferenceGraphGenerator(self.__object_generator)
        self.__config = config or Config()
        self.__stix_version = stix_version

    @property
    def config(self):
        return self.__config

    def __random_generatable_stix_type(self, *constraints):
        """
        Wraps stix2generator.utils.random_generatable_stix_type() and does some
        error handling, to avoid repeating it at various call sites.  See the
        aforementioned function for more information.

        :param constraints: Constraints describing STIX types
        :return: A satisfying generatable STIX type
        :raises stix2generator.exceptions.GeneratableSTIXTypeNotFoundError: if
            a satisfying generatable STIX type could not be found
        """
        stix_type = stix2generator.utils.random_generatable_stix_type(
            self.__object_generator, *constraints,
            stix_version=self.__stix_version
        )

        if not stix_type:
            raise stix2generator.exceptions.GeneratableSTIXTypeNotFoundError(
                constraints, self.__stix_version
            )

        return stix_type

    def __make_sro(self, rel, id1, id2, type1=None, type2=None):
        """
        Make an SRO dict of the type reflected by the given Relationship object
        (rel), which connects the given two IDs together.  If the SRO could
        "point" in either direction (id1 -> id2 or id2 -> id1), then a
        direction is chosen at random.

        :param rel: A Relationship object, which gives the required source and
            target types, and the relationship type
        :param id1: The STIX ID of one SRO endpoint
        :param id2: The STIX ID of the other SRO endpoint
        :param type1: The type of id1 if known, None if unknown.  If not
            passed, it is derived from id1.  Prevents having to recompute it,
            if it is already known at a call site.
        :param type2: The type of id2, analogous to type1
        :return: The SRO dict
        """

        if not type1:
            type1 = stix2.utils.get_type_from_id(id1)

        if not type2:
            type2 = stix2.utils.get_type_from_id(id1)

        if type1 == type2:
            # let it be 50-50 which way we point the SRO, if it can
            # point either way.
            source_ref = id1
            target_ref = id2
            if random.random() < 0.5:
                source_ref, target_ref = target_ref, source_ref

        elif type1 == rel.src_type:
            source_ref = id1
            target_ref = id2

        else:
            source_ref = id2
            target_ref = id1

        sro = self.__object_generator.generate("relationship")
        sro["source_ref"] = source_ref
        sro["target_ref"] = target_ref
        sro["relationship_type"] = rel.rel_type

        return sro

    def __make_related_to_sro(self, id1, id2):
        """
        Make a "related-to" SRO connecting id1 and id2.  The directionality of
        the SRO will be randomly chosen.

        :param id1: The STIX ID of an endpoint
        :param id2: The STIX ID of another endpoint
        :return: A related-to SRO dict
        """

        source_ref = id1
        target_ref = id2
        if random.random() < 0.5:
            source_ref, target_ref = target_ref, source_ref

        sro = self.__object_generator.generate("relationship")
        sro["source_ref"] = source_ref
        sro["target_ref"] = target_ref
        sro["relationship_type"] = "related-to"

        return sro

    def __make_ref_graph(self, seed_type, by_id, by_type):
        """
        Make a reference graph seeded with an object of the given type, and
        integrate it into the current STIX graph.  Return the ID of the
        generated seed object.  The graph bookkeeping structures are updated
        in-place.

        :param seed_type: A STIX type
        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        :return: The ID of the generated seed object
        """

        # This is an easy way of being able to see a "delta" between the old
        # content and new.  We need to make a pass through the new content to
        # update our bookkeeping.  Ought to be more efficient than scanning the
        # whole graph each time.
        chained_graph = collections.ChainMap(by_id).new_child()

        seed_id, _ = self.__ref_graph_generator.generate(
            seed_type, chained_graph
        )

        new_content = chained_graph.maps[0]
        by_id.update(new_content)

        for id_, obj in new_content.items():
            by_type.setdefault(obj["type"], []).append(id_)

        return seed_id

    def __complete_ref_properties(self, obj, by_id, by_type):
        """
        Find all ref properties of the given object, and generate additional
        objects and fix up the references such that none are dangling.  The
        object and bookkeeping structures are updated in-place.

        This uses the reference graph generator, which will deal with things
        like inverse property constraints, to ensure a more semantically
        sensible graph.  In most cases, to be safe, this is probably how one
        should deal with reference properties.  In specific cases, where
        there is more assurance that the reference is very generic and there
        is unlikely to be semantic issues with reuse or inverse properties,
        one could choose to do something else to satisfy the reference.  This
        would be the case for source_ref/target_ref in plain SROs, for example.

        :param obj: The object to fix up
        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        """

        for parent, key, id_, _ \
                in stix2generator.utils.find_references_assignable(obj):

            # Don't disturb any references already pointing to an existing
            # object.
            if id_ not in by_id:
                stix_type = stix2.utils.get_type_from_id(id_)
                seed_id = self.__make_ref_graph(stix_type, by_id, by_type)
                parent[key] = seed_id

    def __random_get_id(self, by_id, by_type, *required_types):
        """
        Get an ID of a type satisfying the given constraints, admitting
        randomness in whether the ID of an existing object is returned, or
        whether a new object is created.  If a new object is created, its ref
        properties will be filled out according to config settings.

        When setting a ref property, one should be careful: there is potential
        for violating inverse property constraints or other semantic weirdness.
        See __complete_ref_properties().

        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        :param required_types: Type constraints, as a sequence of STIX type
            strings and/or stix2generator.utils.STIXTypeClass enum values.  A
            type constraint must be given, otherwise no satisfying type will
            exist.
        :return: A STIX ID whose type satisfies the given type constraints
        """

        id_ = None
        if random.random() < self.config.probability_reuse:
            id_ = _random_id_of_types(
                by_type, *required_types, stix_version=self.__stix_version
            )

        # It's possible no existing ID satisfies the constraints; create a new
        # object in that case.
        if not id_:
            stix_type = self.__random_generatable_stix_type(*required_types)
            obj = self.__object_generator.generate(stix_type)
            obj_type = obj["type"]
            id_ = obj["id"]

            by_id[id_] = obj
            by_type.setdefault(obj_type, []).append(id_)

            if self.config.complete_ref_properties:
                self.__complete_ref_properties(obj, by_id, by_type)

        return id_

    def __random_ref_list(self, ref_list, by_id, by_type):
        """
        Fill out a reference list from an object, admitting randomness in
        whether IDs of existing objects are used, or whether new objects are
        created.  The graph bookkeeping structures are updated in-place.  Any
        IDs which already refer to graph nodes are left as-is.  Others are
        replaced with IDs of the same type.

        When setting a ref property, one should be careful: there is potential
        for violating inverse property constraints or other semantic weirdness.
        See __complete_ref_properties().

        :param ref_list: A list of references (STIX IDs)
        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        """
        for idx, ref_id in enumerate(ref_list):
            if ref_id not in by_id:

                stix_type = stix2.utils.get_type_from_id(ref_id)

                new_id = self.__random_get_id(by_id, by_type, stix_type)

                ref_list[idx] = new_id

    def __add_sighting(self, by_id, by_type):
        """
        Create a sighting and add it to the graph.  This is not always
        possible, since all new content must connect to existing content to
        avoid a partitioned result, and the "connection points" of a sighting
        (ref properties) have constraints on what they're allowed to refer to.
        Therefore, if there are no objects currently in the graph we can
        connect a sighting to, we can't create a sighting.  This is different
        from a vanilla relationship, for which we always have a generic fallback
        we can use to relate anything ("related-to").  The graph bookkeeping
        structures are updated in-place.

        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        :return: True if a sighting could be created; False if not
        """

        if any(
                stix2generator.utils.is_sdo(type_, self.__stix_version)
                for type_ in by_type
        ):
            sighting = self.__object_generator.generate("sighting")
            observed_data_refs = sighting.get("observed_data_refs")
            where_sighted_refs = sighting.get("where_sighted_refs")

            # We need to connect this sighting to the existing graph, somehow.
            # There are three ways to do that: sighting_of_ref,
            # observed_data_refs, where_sighted_refs.  We know we can connect
            # via sighting_of_ref since we have at least one SDO.  But let's
            # be random about how we connect, as far as that's possible.

            if random.random() < 0.33 \
                    and observed_data_refs \
                    and "observed-data" in by_type:

                # Connect via random element of observed_data_refs
                observed_data_idx = random.randrange(len(observed_data_refs))
                observed_data_id = _random_id_of_types(
                    by_type, "observed-data", stix_version=self.__stix_version
                )
                observed_data_refs[observed_data_idx] = observed_data_id

            elif random.random() < 0.5 \
                    and where_sighted_refs \
                    and ("identity" in by_type or "location" in by_type):

                # Connect via random element of where_sighted_refs
                where_sighted_idx = random.randrange(len(where_sighted_refs))
                where_sighted_id = _random_id_of_types(
                    by_type, "identity", "location",
                    stix_version=self.__stix_version
                )
                where_sighted_refs[where_sighted_idx] = where_sighted_id

            else:

                # Connect via sighting_of_ref
                sighting_of_id = _random_id_of_types(
                    by_type, stix2generator.utils.STIXTypeClass.SDO,
                    stix_version=self.__stix_version
                )
                sighting["sighting_of_ref"] = sighting_of_id

            # Fill out the rest of the references: these randomly may or may
            # not connect to existing graph nodes.
            if sighting["sighting_of_ref"] not in by_id:
                sighting["sighting_of_ref"] = self.__random_get_id(
                    by_id, by_type, stix2generator.utils.STIXTypeClass.SDO
                )

            if observed_data_refs:
                self.__random_ref_list(observed_data_refs, by_id, by_type)

            if where_sighted_refs:
                self.__random_ref_list(where_sighted_refs, by_id, by_type)

            by_id[sighting["id"]] = sighting
            by_type.setdefault("sighting", []).append(sighting["id"])

            if self.config.complete_ref_properties:
                self.__complete_ref_properties(sighting, by_id, by_type)

            success = True

        else:
            # With no SDOs, we can't connect a sighting to any node currently
            # in the graph.  Therefore, we can't create a sighting.
            success = False

        return success

    def __add_sro_reuse(self, by_id, by_type):
        """
        Add a new SRO to the graph, which connects two existing nodes.  The
        bookkeeping structures are updated in-place.

        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        """

        endpoint_id1 = _random_sro_connectable_id(by_type, self.__stix_version)
        endpoint_type1 = stix2.utils.get_type_from_id(endpoint_id1)

        rels = stix2generator.generation.relationships \
            .RELATIONSHIP_OBJECTS_BY_ENDPOINT_TYPE.get(endpoint_type1, [])

        # The idea here is to choose a uniformly random ID over all IDs in the
        # graph connectable to endpoint_id1.  A simpler way would be to
        # first choose a random relationship, then a random ID, but that would
        # not result in a uniform distribution over IDs.
        #
        # reverse_rels_map maps from "other end" type to a list of the
        # relationship objects usable to connect id1 to that other end.
        reverse_rels_map = {}
        for rel in rels:
            endpoint_type2 = rel.target_type \
                if endpoint_type1 == rel.src_type \
                else rel.src_type
            reverse_rels_map.setdefault(endpoint_type2, []).append(rel)

        endpoint_id2 = _random_id_of_types(
            by_type, *reverse_rels_map,
            stix_version=self.__stix_version
        )

        if endpoint_id2:
            endpoint_type2 = stix2.utils.get_type_from_id(endpoint_id2)
            rel = random.choice(reverse_rels_map[endpoint_type2])

            sro = self.__make_sro(
                rel, endpoint_id1, endpoint_id2,
                endpoint_type1, endpoint_type2
            )

        else:
            # We can't find an SRO to use to connect endpoint_id1 to
            # any other graph node.  So connect it to a random node via
            # related-to.
            endpoint_id2 = _random_sro_connectable_id(
                by_type, self.__stix_version
            )
            sro = self.__make_related_to_sro(endpoint_id1, endpoint_id2)

        by_id[sro["id"]] = sro

        if self.config.complete_ref_properties:
            self.__complete_ref_properties(sro, by_id, by_type)

    def __add_sro_new(self, by_id, by_type):
        """
        Add a new SRO to the graph, which connects an existing node to a new
        node.  The bookkeeping structures are updated in-place.

        :param by_id: The current object graph, as a map from ID to object
        :param by_type: Additional bookkeeping: a map from STIX type to a list
            of IDs of STIX objects in the current graph of that type
        """

        endpoint_id1 = _random_sro_connectable_id(by_type, self.__stix_version)
        endpoint_type1 = stix2.utils.get_type_from_id(endpoint_id1)
        rels = stix2generator.generation.relationships \
            .RELATIONSHIP_OBJECTS_BY_ENDPOINT_TYPE.get(endpoint_type1)

        if rels:
            rel = random.choice(rels)

            endpoint_type2 = rel.target_type \
                if endpoint_type1 == rel.src_type \
                else rel.src_type

            endpoint_object2 = self.__object_generator.generate(
                endpoint_type2
            )
            endpoint_id2 = endpoint_object2["id"]

            sro = self.__make_sro(
                rel, endpoint_id1, endpoint_id2,
                endpoint_type1, endpoint_type2
            )

        else:
            # We know of no SROs usable to connect endpoint_id1 to *any* object
            # type.  So just use related-to with a random type.

            endpoint_type2 = self.__random_generatable_stix_type(
                stix2generator.utils.STIXTypeClass.SDO,
                stix2generator.utils.STIXTypeClass.SCO
            )
            endpoint_object2 = self.__object_generator.generate(
                endpoint_type2
            )
            endpoint_id2 = endpoint_object2["id"]

            sro = self.__make_related_to_sro(endpoint_id1, endpoint_id2)

        by_id[endpoint_id2] = endpoint_object2
        by_type.setdefault(endpoint_type2, []).append(endpoint_id2)
        by_id[sro["id"]] = sro

        if self.config.complete_ref_properties:
            self.__complete_ref_properties(sro, by_id, by_type)
            self.__complete_ref_properties(endpoint_object2, by_id, by_type)

    def generate(self, seed_type=None, preexisting_objects=None):
        """
        Generate a STIX graph seeded with an object of the given type.  When
        object reuse is allowed, preexisting_objects provides a way to reuse
        pre-existing objects.  This can be helpful when larger amounts of graph
        content is built up incrementally, so that new regions of content can
        connect with existing regions, instead of each invocation producing its
        own disconnected "island" of content.

        :param seed_type: A STIX type, STIXTypeClass enum, or None.  Generation
            is done by "building out" from a seed object.  This parameter
            determines the type of the seed object.  If None, a STIX SDO is
            chosen at random.
        :param preexisting_objects: The pre-existing STIX content, as either a
            list of objects or mapping from ID to object.
        :return: the generated content, as a mapping from ID to object.  If
            preexisting_objects was given as a map, the same map is returned,
            updated with the new content.  Otherwise, a new map is created and
            returned.  It will contain all of the data from preexisting_objects
            plus the new content.
        """

        if not seed_type:
            seed_type = stix2generator.utils.STIXTypeClass.SDO

        # Might seem kinda silly if seed_type is directly given as a string,
        # but this ensures that the given seed type is actually generatable
        # with our object generator.
        seed_type = self.__random_generatable_stix_type(
            seed_type
        )

        # Pre-populate our data structures, if we were given pre-existing
        # objects.
        #
        # by_id maps from an object ID to an object.  It will hold all objects
        # in the graph.
        if preexisting_objects:
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

        # by_type maps from a STIX type to a list of object IDs in the graph of
        # that type.
        by_type = {}

        for id_, obj in by_id.items():
            obj_type = stix2.utils.get_type_from_id(id_)
            by_type.setdefault(obj_type, []).append(id_)

        seed_obj = self.__object_generator.generate(seed_type)
        seed_id = seed_obj["id"]
        by_id[seed_id] = seed_obj
        by_type.setdefault(seed_type, []).append(seed_id)

        if self.config.complete_ref_properties:
            self.__complete_ref_properties(seed_obj, by_id, by_type)

        # If no SRO-connectable objects available, we can't do anything more!
        if any(
            _is_sro_connectable(type_, self.__stix_version)
            for type_ in by_type
        ):

            num_rels = random.randint(
                self.config.min_relationships, self.config.max_relationships
            )

            for _ in range(num_rels):

                sighting_success = False
                if random.random() < self.config.probability_sighting:
                    sighting_success = self.__add_sighting(by_id, by_type)

                # It's not always possible to add a sighting.  In case we tried
                # and failed, just add a normal SRO instead.
                if not sighting_success:
                    if random.random() < self.config.probability_reuse \
                            and len(by_id) > 1:
                        # Reuse: connect the other end of the SRO to an existing
                        # object.  But if there's only one node, reuse implies
                        # creating a self-loop (reusing that one single node),
                        # which seems weird semantically.  So lets inhibit reuse
                        # in that specific case.

                        self.__add_sro_reuse(by_id, by_type)

                    else:
                        self.__add_sro_new(by_id, by_type)

        # Parse the new objects we created and incorporate them into the base
        # graph.
        new_objects = by_id.maps[0]
        by_id = by_id.maps[1]
        for new_id, new_obj_dict in new_objects.items():
            by_id[new_id] = stix2.parse(
                new_obj_dict, version=self.__stix_version, allow_custom=True
            )

        return by_id

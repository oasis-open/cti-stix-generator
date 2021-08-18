import sys

import lark.exceptions
import pytest
import rdflib

import stix2generator
from stix2generator.exceptions import (CircularVariableDependenciesError,
                                       LanguageError, RedeclaredVariableError,
                                       SpecificationNotFoundError,
                                       UndeclaredVariableError)

_STIX_URN_PREFIX_ID = "urn:stix:id:"
_STIX_URN_PREFIX_TYPE = "urn:stix:type:"
_SPARQL_NS_PREFIX = """
PREFIX stix_id: <{}>
PREFIX stix_type: <{}>
PREFIX rdfs: <{}>
""".format(
    _STIX_URN_PREFIX_ID,
    _STIX_URN_PREFIX_TYPE,
    rdflib.RDFS
)


def _stix2rdf(objs):
    """
    Convert the given STIX objects to RDF.  This is done very simply: each
    "plain" SRO (i.e. not sightings) is converted to an RDF triple.  Embedded
    references are ignored.  This produces an RDF graph with the same topology
    as the STIX objects.

    A custom URN is used for each STIX object and relationship.  An additional
    custom URN is used to represent object types, so that type information
    can be checked via an RDF query.  STIX object URNs are of the form:

        urn:stix:id:<stix-id>

    STIX type URNs are of the form:

        urn:stix:type:<stix-type>

    STIX object type info is represented via the standard rdf:type property.
    Relationships don't get STIX type triples, but instead get a triple
    representing the relationship type, e.g. "targets", "uses", etc.  This is
    done via a rdfs:label triple whose object is the literal type string.

    :param objs: A list of STIX objects
    :return: An RDF graph
    """

    # Extract the relationships; create a id->obj lookup table for quick
    # reference resolution.
    rels = []
    id_to_obj = {}
    for obj in objs:
        if obj.type == "relationship":
            rels.append(obj)

        id_to_obj[obj.id] = obj

    g = rdflib.Graph()
    g.namespace_manager.bind("stix_id", _STIX_URN_PREFIX_ID)
    g.namespace_manager.bind("stix_type", _STIX_URN_PREFIX_TYPE)

    for rel in rels:
        urn_source = rdflib.URIRef(_STIX_URN_PREFIX_ID + rel.source_ref)
        urn_source_type = rdflib.URIRef(
            _STIX_URN_PREFIX_TYPE + id_to_obj[rel.source_ref].type
        )

        urn_target = rdflib.URIRef(_STIX_URN_PREFIX_ID + rel.target_ref)
        urn_target_type = rdflib.URIRef(
            _STIX_URN_PREFIX_TYPE + id_to_obj[rel.target_ref].type
        )

        urn_rel = rdflib.URIRef(_STIX_URN_PREFIX_ID + rel.id)

        # Add anything into the graph we want to test for in queries.

        # Triple representing the relationship
        g.add((urn_source, urn_rel, urn_target))

        # Triples representing object types.  I think we won't bother with
        # a triple for the relationship.  If it's relating two things, I think
        # that's implied, for our purposes.
        g.add((urn_source, rdflib.RDF.type, urn_source_type))
        g.add((urn_target, rdflib.RDF.type, urn_target_type))

        # Triple representing the relationship type.  Will just (ab)use the
        # built-in rdfs:label property for this for now.
        g.add(
            (urn_rel, rdflib.RDFS.label, rdflib.Literal(rel.relationship_type))
        )

    return g


def _graph_match(stix_objs, sparql_pattern):
    """
    Check the graph topology of the given STIX objects.  This function converts
    the given objects to RDF, and then checks the given SPARQL query for a
    match.

    The query pattern should not be passed as a complete query; to reduce
    repetition, only the body of an "ASK" query must be passed.  The pattern
    will automatically be wrapped in "ASK { ... }" and prefixed with some
    standard prefix definitions.

    :param stix_objs: A list of STIX objects
    :param sparql_pattern: A bare SPARQL query body
    :return:
    """
    rdf_graph = _stix2rdf(stix_objs)

    # May as well factor this out here, so we don't have to repeat it in the
    # pattern construction of every single test...
    sparql_pattern = """
    {}
    ASK
    {{
    {}
    }}
    """.format(
        _SPARQL_NS_PREFIX,
        sparql_pattern
    )

    # This is a simple documented way to get the bool result of an "ASK"
    # query.
    # https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.query.Result
    return bool(rdf_graph.query(sparql_pattern))


def _debug_graph_select(stix_objs, sparql_pattern):
    """
    For debugging SPARQL queries: performs a SELECT query and prints out all
    variable bindings in all results.  Also prints the RDF graph being queried,
    in Turtle format.

    :param stix_objs: A list of STIX objects
    :param sparql_pattern: A SPARQL pattern, without the extra prefixes,
        "SELECT", etc.  Just the guts of it, between the braces.
        SELECT * WHERE { ... } is wrapped around it automatically.
    """
    rdf_graph = _stix2rdf(stix_objs)

    print("RDF Graph:")
    rdf_graph.serialize(sys.stdout, "turtle")

    sparql_pattern = """
    {}
    SELECT *
    WHERE {{
    {}
    }}
    """.format(
        _SPARQL_NS_PREFIX,
        sparql_pattern
    )

    print("Bindings:")
    for result in rdf_graph.query(sparql_pattern):
        for name in result.labels:
            print(name, ":", result[name])
        print()


@pytest.fixture(scope="module")
def processor():
    return stix2generator.create_default_language_processor(stix_version="2.1")


def test_basic(processor):
    objs = processor.build_graph("Identity.")

    assert len(objs) == 1

    identity = objs[0]
    assert(identity.type == "identity")


def test_basic_count(processor):
    objs = processor.build_graph("2 Identity.")

    assert len(objs) == 2

    assert all(obj.type == "identity" for obj in objs)


def test_basic_rel(processor):
    objs = processor.build_graph("Malware targets Identity.")

    pattern = """
    ?m a stix_type:malware .
    ?i a stix_type:identity .
    ?r rdfs:label "targets" .
    ?m ?r ?i .
    """

    assert _graph_match(objs, pattern)


def test_basic_rel_source_count(processor):
    objs = processor.build_graph("2 Malware targets Identity.")

    pattern = """
    ?m1 a stix_type:malware .
    ?m2 a stix_type:malware .
    ?i a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?m1 ?r1 ?i .
    ?m2 ?r2 ?i .
    FILTER (?m1 != ?m2 && ?r1 != ?r2)
    """

    assert _graph_match(objs, pattern)


def test_basic_rel_rel_count(processor):
    objs = processor.build_graph("Malware 2 targets Identity.")

    pattern = """
    ?m a stix_type:malware .
    ?i a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?m ?r1 ?i .
    ?m ?r2 ?i .
    FILTER (?r1 != ?r2)
    """

    assert _graph_match(objs, pattern)


def test_basic_rel_target_count(processor):
    objs = processor.build_graph("Malware targets 2 Identity.")

    pattern = """
    ?m a stix_type:malware .
    ?i1 a stix_type:identity .
    ?i2 a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?m ?r1 ?i1 .
    ?m ?r2 ?i2 .
    FILTER (?r1 != ?r2 && ?i1 != ?i2)
    """

    assert _graph_match(objs, pattern)


def test_basic_rel_source_rel_count(processor):
    objs = processor.build_graph("2 Malware 2 targets Identity.")

    # I wish there was a simple way to tell the SPARQL engine that distinct
    # variable names must bind to distinct values!
    pattern = """
    ?m1 a stix_type:malware .
    ?m2 a stix_type:malware .
    ?i a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?r3 rdfs:label "targets" .
    ?r4 rdfs:label "targets" .
    ?m1 ?r1 ?i .
    ?m1 ?r2 ?i .
    ?m2 ?r3 ?i .
    ?m2 ?r4 ?i .
    FILTER (
        ?m1 != ?m2
        && ?r1 != ?r2
        && ?r3 != ?r4
    )
    """
    # Note: don't need to check the r1/r3 and r2/r4 combinations.  If those
    # were equal, it would imply the same relationship has two values for
    # source_ref, which is impossible (since we require ?m1 != ?m2).

    assert _graph_match(objs, pattern)


def test_basic_rel_source_target_count(processor):
    objs = processor.build_graph("2 Malware targets 2 Identity.")

    pattern = """
    ?m1 a stix_type:malware .
    ?m2 a stix_type:malware .
    ?i1 a stix_type:identity .
    ?i2 a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?r3 rdfs:label "targets" .
    ?r4 rdfs:label "targets" .
    ?m1 ?r1 ?i1 .
    ?m1 ?r2 ?i2 .
    ?m2 ?r3 ?i1 .
    ?m2 ?r4 ?i2 .
    FILTER (
        ?m1 != ?m2
        && ?i1 != ?i2
    )
    """
    # Don't have to check any ?r's here.  Due to ?m/?i requirements, all
    # source/target pairs are distinct, so it would be impossible to reuse
    # the same SRO binding for any of them.

    assert _graph_match(objs, pattern)


def test_basic_rel_rel_target_count(processor):
    objs = processor.build_graph("Malware 2 targets 2 Identity.")

    pattern = """
    ?m a stix_type:malware .
    ?i1 a stix_type:identity .
    ?i2 a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?r3 rdfs:label "targets" .
    ?r4 rdfs:label "targets" .
    ?m ?r1 ?i1 .
    ?m ?r2 ?i1 .
    ?m ?r3 ?i2 .
    ?m ?r4 ?i2 .
    FILTER (
        ?i1 != ?i2
        && ?r1 != ?r2
        && ?r3 != ?r4
    )
    """

    assert _graph_match(objs, pattern)


def test_basic_rel_source_rel_target_count(processor):
    objs = processor.build_graph("2 Malware 2 targets 2 Identity.")

    # pattern = """
    # ?m1 a stix_type:malware .
    # ?m2 a stix_type:malware .
    # ?i1 a stix_type:identity .
    # ?i2 a stix_type:identity .
    #
    # ?r1 rdfs:label "targets" .
    # ?r2 rdfs:label "targets" .
    # ?r3 rdfs:label "targets" .
    # ?r4 rdfs:label "targets" .
    # ?r5 rdfs:label "targets" .
    # ?r6 rdfs:label "targets" .
    # ?r7 rdfs:label "targets" .
    # ?r8 rdfs:label "targets" .
    #
    # ?m1 ?r1 ?i1 .
    # ?m1 ?r2 ?i1 .
    # ?m1 ?r3 ?i2 .
    # ?m1 ?r4 ?i2 .
    # ?m2 ?r5 ?i1 .
    # ?m2 ?r6 ?i1 .
    # ?m2 ?r7 ?i2 .
    # ?m2 ?r8 ?i2 .
    #
    # FILTER (
    #     ?i1 != ?i2
    #     && ?m1 != ?m2
    #     && ?r1 != ?r2
    #     && ?r3 != ?r4
    #     && ?r5 != ?r6
    #     && ?r7 != ?r8
    # )
    # """
    #
    # assert _graph_match(objs, pattern)
    #
    # Takes too long... ~ 6 mins on my laptop.  I hoped that with an "ASK"
    # query, the SPARQL processor would be smart enough to return on the first
    # binding found.  But I don't think it works that way... it still wastes
    # time finding ALL bindings.  Sigh...

    # So do some simple checks instead.
    assert len(objs) == 12

    counts_by_type = {}
    for obj in objs:
        count = counts_by_type.get(obj.type, 0)
        count += 1
        counts_by_type[obj.type] = count

    assert counts_by_type == {
        "malware": 2,
        "identity": 2,
        "relationship": 8
    }

    pass


def test_chain_rel(processor):
    objs = processor.build_graph("Campaign uses Malware targets Identity.")

    pattern = """
    ?c a stix_type:campaign .
    ?m a stix_type:malware .
    ?r1 rdfs:label "uses" .
    ?r2 rdfs:label "targets" .
    ?c ?r1 ?m .
    ?m ?r2 ?i .
    """

    assert _graph_match(objs, pattern)


def test_paren_target(processor):
    objs = processor.build_graph(
        "Attack_Pattern targets (Identity Vulnerability)."
    )

    pattern = """
    ?ap a stix_type:attack-pattern .
    ?i a stix_type:identity .
    ?v a stix_type:vulnerability .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?ap ?r1 ?i .
    ?ap ?r2 ?v .
    """

    assert _graph_match(objs, pattern)


def test_paren_source(processor):
    objs = processor.build_graph(
        "(Attack_Pattern Campaign) targets Identity."
    )

    pattern = """
    ?ap a stix_type:attack-pattern .
    ?c a stix_type:campaign .
    ?i a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?ap ?r1 ?i .
    ?c ?r2 ?i .
    """

    assert _graph_match(objs, pattern)


def test_basic_variable(processor):
    objs = processor.build_graph("""
    i : Identity .
    i .
    """)

    assert len(objs) == 1
    assert objs[0].type == "identity"


def test_basic_variable_count(processor):
    objs = processor.build_graph("""
    2 i : Identity .
    i .
    """)

    assert len(objs) == 2
    assert all(obj.type == "identity" for obj in objs)


def test_variable_count_rel(processor):
    objs = processor.build_graph("""
    2 m : Malware .
    i : Identity .
    m targets i .
    """)

    pattern = """
    ?m1 a stix_type:malware .
    ?m2 a stix_type:malware .
    ?i a stix_type:identity .
    ?r1 rdfs:label "targets" .
    ?r2 rdfs:label "targets" .
    ?m1 ?r1 ?i .
    ?m2 ?r2 ?i .
    FILTER(?m1 != ?m2)
    """

    assert _graph_match(objs, pattern)


def test_property_block(processor):
    objs = processor.build_graph("""
    Grouping {
        object_refs: (Identity Location)
    } .
    """)

    assert len(objs) == 3
    g = i = ell = None
    for obj in objs:
        if obj.type == "grouping":
            g = obj
        elif obj.type == "identity":
            i = obj
        elif obj.type == "location":
            ell = obj
        else:
            raise Exception("Unexpected object: " + obj.id)

    assert g.object_refs == [i.id, ell.id]


def test_property_block_string(processor):
    objs = processor.build_graph("""
    Attack_Pattern {
        name: "a name"
    } .
    """)

    assert len(objs) == 1
    assert objs[0].name == "a name"


def test_property_block_string_list(processor):
    objs = processor.build_graph("""
    Attack_Pattern {
        aliases: ["alias1", "alias2"]
    } .
    """)

    assert len(objs) == 1
    assert objs[0].aliases == ["alias1", "alias2"]


def test_property_block_variable(processor):
    objs = processor.build_graph("""
    ap {
        name: "a name"
    } : Attack_Pattern .

    ap targets Identity .
    """)

    pattern = """
    ?ap a stix_type:attack-pattern .
    ?i a stix_type:identity .
    ?r rdfs:label "targets" .
    ?ap ?r ?i .
    """

    _graph_match(objs, pattern)

    aps = [obj for obj in objs if obj.type == "attack-pattern"]
    assert len(aps) == 1
    assert aps[0].name == "a name"


def test_property_block_variable_dependencies(processor):
    objs = processor.build_graph("""
    g { object_refs: i } : Grouping .
    2 i : Identity .
    g .
    """)

    g = None
    i = []
    for obj in objs:
        if obj.type == "grouping":
            g = obj
        elif obj.type == "identity":
            i.append(obj)
        else:
            raise Exception("Unexpected object: " + obj.id)

    assert len(objs) == 3
    assert len(g.object_refs) == 2
    assert len(i) == 2
    assert i[0].id in g.object_refs
    assert i[1].id in g.object_refs


def test_property_block_variable_dependencies_circular(processor):
    with pytest.raises(CircularVariableDependenciesError):
        processor.build_graph("""
        g { object_refs: n } : Grouping .
        n { object_refs: g } : Note .
        g .
        """)


def test_variable_undefined(processor):
    with pytest.raises(lark.exceptions.VisitError) as e:
        processor.build_graph("""
        Malware targets i .
        """)

    assert isinstance(e.value.orig_exc, UndeclaredVariableError)
    assert e.value.orig_exc.var_name == "i"


def test_variable_redeclared(processor):
    with pytest.raises(lark.exceptions.VisitError) as e:
        processor.build_graph("""
        i : Identity .
        i : Identity .
        i .
        """)

    assert isinstance(e.value.orig_exc, RedeclaredVariableError)
    assert e.value.orig_exc.var_name == "i"


def test_on(processor):
    objs = processor.build_graph("""
    Report on (Identity Malware) .
    """)

    assert len(objs) == 3
    r = i = m = None
    for obj in objs:
        if obj.type == "report":
            r = obj
        elif obj.type == "identity":
            i = obj
        elif obj.type == "malware":
            m = obj
        else:
            raise Exception("Unexpected object: " + obj.id)

    assert r.object_refs == [i.id, m.id]


def test_on_count(processor):
    with pytest.raises(lark.exceptions.VisitError) as e:
        # Can't have count > 1 for "on".
        processor.build_graph("""
        Report 2 on (Identity Malware) .
        """)

    assert isinstance(e.value.orig_exc, LanguageError)


def test_sighting(processor):
    objs = processor.build_graph("""
    Sighting of Malware .
    """)

    assert len(objs) == 2
    s = m = None
    for obj in objs:
        if obj.type == "sighting":
            s = obj
        elif obj.type == "malware":
            m = obj
        else:
            raise Exception("Unexpected object: " + obj.id)

    assert s.sighting_of_ref == m.id


def test_sighting_dupe_sighting_of_ref(processor):
    with pytest.raises(lark.exceptions.VisitError) as e:
        # Sighting target (sighting_of_ref) can't be given via "of" and a
        # property block at the same time.
        processor.build_graph("""
        Sighting {sighting_of_ref: Malware} of Malware .
        """)

    assert isinstance(e.value.orig_exc, LanguageError)


def test_sighting_count(processor):
    with pytest.raises(lark.exceptions.VisitError) as e:
        # Adding a count to "of" or "Sighting" changes the parse: this is
        # recognized as a plain relationship with a source type of "Sighting",
        # not the specially handled sighting syntax.  It results in an error
        # about a spec not being found, since there is no "Sighting"
        # specification in the object generator registry.
        processor.build_graph("""
        Sighting 2 of Malware .
        """)

    assert isinstance(e.value.orig_exc, SpecificationNotFoundError)

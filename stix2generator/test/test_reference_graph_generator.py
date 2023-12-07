import copy

import pytest
import stix2
import stix2.base
import stix2.utils

import stix2generator
import stix2generator.generation.object_generator
import stix2generator.generation.reference_graph_generator
import stix2generator.generation.semantics
import stix2generator.test.utils

_TLP_MARKING_DEFINITION_IDS = {
    "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",
    "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
    "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82",
    "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed",
}


@pytest.mark.parametrize(
    "seed_type", [
        "identity",
        stix2.utils.STIXTypeClass.SDO,
        stix2.utils.STIXTypeClass.SCO,
        stix2.utils.STIXTypeClass.SRO
    ]
)
def test_seeds(num_trials, seed_type):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    ref_graph_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(obj_gen, stix_version="2.1")

    for _ in range(num_trials):

        _, graph = ref_graph_gen.generate(seed_type)

        # Ensure the graph has at least one object of type seed_type.
        assert any(
            stix2.utils.is_stix_type(
                obj, "2.1", seed_type
            )
            for obj in graph.values()
        )


def test_bad_seed():
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    ref_graph_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(obj_gen, stix_version="2.1")

    with pytest.raises(
        stix2generator.exceptions.GeneratableSTIXTypeNotFoundError
    ):
        ref_graph_gen.generate("foo")


def _reverse_constraint(constraint):
    """
    Creates a "reversed" constraint: a constraint where the object types and
    property names have been reversed.
    :param constraint: A inverse property constraint object
    :return: The reversed constraint object
    """
    reversed_ = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint(
            constraint.object_type2, constraint.prop_name2,
            constraint.object_type1, constraint.prop_name1
        )

    return reversed_


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": "3"}),

        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": ["99", "3"]}),

        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": "3"}),

        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": ["99", "3"]}),
    ]
)
def test_inverse_property_constraint_applicable_diff_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type2", "prop2")

    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert reversed_constraint.is_applicable(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "3"}, {"id": "2", "type": "type1", "prop1": "3", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "3", "prop2": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "3"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": "99", "prop2": ["99", "3"]}),
    ]
)
def test_inverse_property_constraint_applicable_same_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop2")

    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert reversed_constraint.is_applicable(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": "1"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": "3"})
    ]
)
def test_inverse_property_constraint_applicable_same_types_props(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop1")

    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert reversed_constraint.is_applicable(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, ref_prop, dest_obj", [
        # wrong references
        ({"id": "1", "type": "type1", "prop1": "3"}, "prop1", {"id": "2", "type": "type2", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["3", "99"]}, "prop1", {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": "3"}, "prop1", {"id": "2", "type": "type2", "prop2": ["4", "1"]}),

        # wrong properties
        ({"id": "1", "type": "type1", "prop1": "2"}, "prop4", {"id": "2", "type": "type2", "prop4": "1"}),
        ({"id": "1", "type": "type1", "prop3": ["2", "99"]}, "prop2", {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop3": "2"}, "prop1", {"id": "2", "type": "type2", "prop4": ["99", "1"]}),

        # wrong types
        ({"id": "1", "type": "type3", "prop1": "2"}, "prop1", {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, "prop1", {"id": "2", "type": "type4", "prop2": "1"}),
        ({"id": "1", "type": "type3", "prop1": "2"}, "prop1", {"id": "2", "type": "type4", "prop2": ["99", "1"]}),
    ]
)
def test_inverse_property_constraint_not_applicable_diff_types(src_obj, ref_prop, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type2", "prop2")

    assert not inv_prop_constraint.is_applicable(src_obj, ref_prop, dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert not reversed_constraint.is_applicable(src_obj, ref_prop, dest_obj)


@pytest.mark.parametrize(
    "src_obj, ref_prop, dest_obj", [
        # wrong references
        ({"id": "1", "type": "type1", "prop1": "3", "prop2": "2"}, "prop1", {"id": "2", "type": "type1", "prop1": "1", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["3", "99"], "prop2": "3"}, "prop1", {"id": "2", "type": "type1", "prop1": "1", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": "3", "prop2": "1"}, "prop1", {"id": "2", "type": "type1", "prop1": "2", "prop2": ["4", "1"]}),

        # wrong properties
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "3"}, "prop1", {"id": "2", "type": "type1", "prop4": "1"}),
        ({"id": "1", "type": "type1", "prop3": ["2", "99"]}, "prop1", {"id": "2", "type": "type1", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop3": "2"}, "prop1", {"id": "2", "type": "type1", "prop4": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "3"}, "prop3", {"id": "2", "type": "type1", "prop1": ["99", "1"], "prop2": "3"}),
    ]
)
def test_inverse_property_constraint_not_applicable_same_types(src_obj, ref_prop, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop2")

    assert not inv_prop_constraint.is_applicable(src_obj, ref_prop, dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert not reversed_constraint.is_applicable(src_obj, ref_prop, dest_obj)


@pytest.mark.parametrize(
    "src_obj, ref_prop, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "3"}, "prop1", {"id": "2", "type": "type1", "prop1": "1"}),
        ({"id": "1", "type": "type1", "prop1": "3"}, "prop1", {"id": "2", "type": "type1", "prop1": "3"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, "prop2", {"id": "2", "type": "type1", "prop1": "1"}),
        ({"id": "1", "type": "type2", "prop1": "2"}, "prop1", {"id": "2", "type": "type1", "prop1": "1"}),
        ({"id": "1", "type": "type1", "prop2": "2"}, "prop1", {"id": "2", "type": "type1", "prop1": "1"}),
    ]
)
def test_inverse_property_constraint_not_applicable_same_types_props(src_obj, ref_prop, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop1")

    assert not inv_prop_constraint.is_applicable(src_obj, ref_prop, dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert not reversed_constraint.is_applicable(src_obj, ref_prop, dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": ["99", "1"]}),
    ]
)
def test_inverse_property_constraint_holds_diff_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type2", "prop2")

    # Ensure I didn't mess up the test case...
    # .holds() assumes .is_applicable().
    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    assert inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert reversed_constraint.holds(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "4", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "4", "prop2": "1"}),
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "99"}, {"id": "2", "type": "type1", "prop1": "2", "prop2": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "99"}, {"id": "2", "type": "type1", "prop1": "2", "prop2": ["99", "1"]}),
    ]
)
def test_inverse_property_constraint_holds_same_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop2")

    # Ensure I didn't mess up the test case...
    # .holds() assumes .is_applicable().
    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    assert inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert reversed_constraint.holds(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": "1"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": "1"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": ["99", "1"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": ["99", "1"]}),
    ]
)
def test_inverse_property_constraint_holds_same_types_props(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop1")

    # Ensure I didn't mess up the test case...
    # .holds() assumes .is_applicable().
    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    assert inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert reversed_constraint.holds(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": ["2", "99"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": ["99", "2"]}),
    ]
)
def test_inverse_property_constraint_not_holds_diff_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type2", "prop2")

    # Ensure I didn't mess up the test case...
    # .holds() assumes .is_applicable().
    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    assert not inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert not reversed_constraint.holds(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": ["4", "99"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": ["99", "4"]}),
    ]
)
def test_inverse_property_constraint_not_holds_same_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop2")

    # Ensure I didn't mess up the test case...
    # .holds() assumes .is_applicable().
    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    assert not inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert not reversed_constraint.holds(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": "2"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": "3"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": ["2", "3"]}),
    ]
)
def test_inverse_property_constraint_not_holds_same_types_props(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop1")

    # Ensure I didn't mess up the test case...
    # .holds() assumes .is_applicable().
    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)

    assert not inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    assert not reversed_constraint.holds(src_obj, "prop1", dest_obj)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type2", "prop2": ["4", "99"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type2", "prop2": ["4", "99"]}),
    ]
)
def test_inverse_property_constraint_enforce_diff_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type2", "prop2")

    # Copies for reverse test to work on
    src_copy = copy.deepcopy(src_obj)
    dest_copy = copy.deepcopy(dest_obj)

    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)
    inv_prop_constraint.enforce(src_obj, "prop1", dest_obj)
    assert inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    reversed_constraint.enforce(src_copy, "prop1", dest_copy)
    assert reversed_constraint.holds(src_copy, "prop1", dest_copy)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "2", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "2"}, {"id": "2", "type": "type1", "prop1": "3", "prop2": "4"}),
        ({"id": "1", "type": "type1", "prop1": "2", "prop2": "3"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": ["4", "99"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"], "prop2": "3"}, {"id": "2", "type": "type1", "prop1": "1", "prop2": ["4", "99"]}),
    ]
)
def test_inverse_property_constraint_enforce_same_types(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop2")

    # Copies for reverse test to work on
    src_copy = copy.deepcopy(src_obj)
    dest_copy = copy.deepcopy(dest_obj)

    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)
    inv_prop_constraint.enforce(src_obj, "prop1", dest_obj)
    assert inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    reversed_constraint.enforce(src_copy, "prop1", dest_copy)
    assert reversed_constraint.holds(src_copy, "prop1", dest_copy)


@pytest.mark.parametrize(
    "src_obj, dest_obj", [
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": "3"}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": "3"}),
        ({"id": "1", "type": "type1", "prop1": "2"}, {"id": "2", "type": "type1", "prop1": ["4", "99"]}),
        ({"id": "1", "type": "type1", "prop1": ["2", "99"]}, {"id": "2", "type": "type1", "prop1": ["4", "99"]}),
    ]
)
def test_inverse_property_constraint_enforce_same_types_props(src_obj, dest_obj):
    inv_prop_constraint = stix2generator.generation.reference_graph_generator\
        .InversePropertyConstraint("type1", "prop1", "type1", "prop1")

    # Copies for reverse test to work on
    src_copy = copy.deepcopy(src_obj)
    dest_copy = copy.deepcopy(dest_obj)

    assert inv_prop_constraint.is_applicable(src_obj, "prop1", dest_obj)
    inv_prop_constraint.enforce(src_obj, "prop1", dest_obj)
    assert inv_prop_constraint.holds(src_obj, "prop1", dest_obj)

    reversed_constraint = _reverse_constraint(inv_prop_constraint)
    reversed_constraint.enforce(src_copy, "prop1", dest_copy)
    assert reversed_constraint.holds(src_copy, "prop1", dest_copy)


@pytest.mark.parametrize(
    "graph, src_id, dest_id", [
        ([{"id": "1", "type": "foo", "prop1_ref": "2"}, {"id": "2", "type": "bar"}], "1", "2"),
        ([{"id": "1", "type": "foo", "prop1_ref": "2"}, {"id": "2", "type": "bar", "prop2_ref": "1"}], "1", "2"),
        ([{"id": "1", "type": "foo", "prop1_ref": "2"}, {"id": "2", "type": "bar", "prop2_ref": "1"}], "2", "1"),
        ([{"id": "1", "type": "foo", "prop1_refs": ["2", "3"]}, {"id": "2", "type": "bar"}], "1", "2"),
        ([{"id": "1", "type": "foo", "prop1_ref": "1"}], "1", "1"),
    ]
)
def test_is_reachable(graph, src_id, dest_id):
    # easier to give a list and derive the mapping
    by_id = {
        obj["id"]: obj
        for obj in graph
    }

    assert stix2generator.generation.reference_graph_generator._is_reachable(
        src_id, dest_id, by_id
    )


@pytest.mark.parametrize(
    "graph, src_id, dest_id", [
        ([{"id": "1", "type": "foo", "prop1_ref": "2"}, {"id": "2", "type": "bar"}], "2", "1"),
        ([{"id": "1", "type": "foo", "prop1_ref": "2"}, {"id": "2", "type": "bar"}, {"id": "3", "type": "baz", "prop3_ref": "2"}], "1", "3"),
        ([{"id": "1", "type": "foo", "prop1_ref": "2"}, {"id": "2", "type": "bar", "prop2_ref": "3"}, {"id": "3", "type": "baz"}], "3", "1")
    ]
)
def test_is_not_reachable(graph, src_id, dest_id):
    # easier to give a list and derive the mapping
    by_id = {
        obj["id"]: obj
        for obj in graph
    }

    assert not stix2generator.generation.reference_graph_generator._is_reachable(
        src_id, dest_id, by_id
    )


def test_find_property_constraints_process():
    src_obj = {
        "id": "1",
        "type": "process",
        "child_refs": ["2"]
    }

    dest_obj = {
        "id": "2",
        "type": "process",
        "parent_ref": "1"
    }

    constraints = stix2generator.generation.reference_graph_generator\
        ._find_property_constraints(src_obj, "child_refs", dest_obj)
    constraints = list(constraints)  # collect them all into a list.
    assert len(constraints) == 1
    assert constraints[0].object_type1 == "process" \
        and constraints[0].object_type2 == "process" \
        and "child_refs" in (
            constraints[0].prop_name1, constraints[0].prop_name2
        )


def test_find_property_constraints_directory():
    src_obj = {
        "id": "1",
        "type": "directory",
        "contains_refs": ["2", "3"]
    }

    dest_obj = {
        "id": "2",
        "type": "file",
        "parent_directory_ref": "1"
    }

    constraints = stix2generator.generation.reference_graph_generator\
        ._find_property_constraints(src_obj, "contains_refs", dest_obj)
    constraints = list(constraints)  # collect them all into a list.
    assert len(constraints) == 1
    constraint = constraints[0]
    # the constraint could be defined either way, so lets allow either
    assert (
        constraint.object_type1 == "directory"
        and constraint.prop_name1 == "contains_refs"
        and constraint.object_type2 == "file"
        and constraint.prop_name2 == "parent_directory_ref"
    ) or (
        constraint.object_type1 == "file"
        and constraint.prop_name1 == "parent_directory_ref"
        and constraint.object_type2 == "directory"
        and constraint.prop_name2 == "contains_refs"
    )


def test_find_property_constraints_missing_inverse():
    src_obj = {
        "id": "1",
        "type": "directory",
        "contains_refs": ["2", "3"]
    }

    dest_obj = {
        "id": "2",
        "type": "file"
        # inverse property is missing, so no constraint is applicable
    }

    constraints = stix2generator.generation.reference_graph_generator\
        ._find_property_constraints(src_obj, "contains_refs", dest_obj)
    constraints = list(constraints)  # collect them all into a list.
    assert not constraints


@pytest.mark.parametrize(
    "src_obj_type, ref_prop, dest_obj_type", [
        # just pick some types/props we know imply constraints
        ("process", "child_refs", "process"),
        ("process", "parent_ref", "process"),
        ("network-traffic", "encapsulates_refs", "network-traffic"),
        ("directory", "contains_refs", "file")
    ]
)
def test_would_be_constrained(src_obj_type, ref_prop, dest_obj_type):
    assert stix2generator.generation.reference_graph_generator\
        ._would_be_constrained(src_obj_type, ref_prop, dest_obj_type)


@pytest.mark.parametrize(
    "src_obj_type, ref_prop, dest_obj_type", [
        ("file", "content_ref", "artifact"),
        ("network-traffic", "object_marking_refs", "marking-definition"),
        ("process", "image_ref", "file"),
    ]
)
def test_would_not_be_constrained(src_obj_type, ref_prop, dest_obj_type):
    assert not stix2generator.generation.reference_graph_generator\
        ._would_be_constrained(src_obj_type, ref_prop, dest_obj_type)


@pytest.mark.parametrize(
    "src_obj, ref_prop, dest_obj", [
        (
            {
                "id": "1",
                "type": "file",
                "parent_directory_ref": "2"
            },
            "parent_directory_ref",
            {
                "id": "2",
                "type": "directory",
                "contains_refs": "4"
            }
        ),
        (
            {
                "id": "1",
                "type": "process",
                "parent_ref": "2"
            },
            "parent_ref",
            {
                "id": "2",
                "type": "process",
                "child_refs": ["4", "99"]
            }
        )
    ]
)
def test_delete_inverse_properties(src_obj, ref_prop, dest_obj):

    # check at least one constraint applies first...
    assert any(
        constraint.is_applicable(src_obj, ref_prop, dest_obj)
        for constraint in stix2generator.generation.reference_graph_generator._INVERSE_PROPERTIES
    )

    stix2generator.generation.reference_graph_generator\
        ._delete_inverse_properties(
            src_obj, ref_prop, dest_obj
        )

    # now, none should apply.
    assert all(
        not constraint.is_applicable(src_obj, ref_prop, dest_obj)
        for constraint in stix2generator.generation.reference_graph_generator._INVERSE_PROPERTIES
    )


def test_no_dangling_references(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)
    ref_graph_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(
            obj_gen
        )

    for _ in range(num_trials):
        _, graph = ref_graph_gen.generate()
        assert not stix2generator.test.utils.has_dangling_references(graph)


def _has_cycle(graph):

    # This is kinda silly, doing repeated reachability tests (a single DFS
    # through the graph would be more efficient), but it's simple to write and
    # should suffice for a unit test right?
    for id_, obj in graph.items():
        for _, ref_id in stix2generator.utils.find_references(obj):
            if stix2generator.generation.reference_graph_generator\
                    ._is_reachable(
                        ref_id, id_, graph
                    ):
                result = True
                break
        else:
            continue

        break
    else:
        result = False

    return result


def _has_reuse(graph):

    # Maps an object ID to another ID which refers to it (via some ref
    # property).
    referrers = {}

    for id_, obj in graph.items():
        for _, ref_id in stix2generator.utils.find_references(obj):
            if ref_id in _TLP_MARKING_DEFINITION_IDS:
                # We *must* reuse these because they have fixed IDs, so ignore
                # them.
                continue

            other_referrer_id = referrers.get(ref_id)
            if other_referrer_id is None:
                referrers[ref_id] = id_

            else:
                result = True
                break
        else:
            continue

        break

    else:
        result = False

    return result


def test_graph_tree(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)
    graph_gen_config = stix2generator.generation.reference_graph_generator\
        .Config(
            graph_type="tree",
            inverse_property_constraints="delete"
        )

    ref_graph_gen = stix2generator.generation.reference_graph_generator\
        .ReferenceGraphGenerator(obj_gen, graph_gen_config)

    for _ in range(num_trials):
        _, graph = ref_graph_gen.generate()
        assert not _has_cycle(graph)
        assert not _has_reuse(graph)
        assert not stix2generator.test.utils.has_dangling_references(graph)
        assert stix2generator.test.utils.is_connected(graph)


def test_graph_dag(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)
    graph_gen_config = stix2generator.generation.reference_graph_generator\
        .Config(
            graph_type="dag",
            inverse_property_constraints="delete"
        )

    ref_graph_gen = stix2generator.generation.reference_graph_generator\
        .ReferenceGraphGenerator(obj_gen, graph_gen_config)

    for _ in range(num_trials):
        _, graph = ref_graph_gen.generate()
        assert not _has_cycle(graph)
        assert not stix2generator.test.utils.has_dangling_references(graph)
        assert stix2generator.test.utils.is_connected(graph)


def test_graph_random(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)
    graph_gen_config = stix2generator.generation.reference_graph_generator\
        .Config(
            graph_type="random",
            inverse_property_constraints="delete"
        )

    ref_graph_gen = stix2generator.generation.reference_graph_generator\
        .ReferenceGraphGenerator(obj_gen, graph_gen_config)

    for _ in range(num_trials):
        _, graph = ref_graph_gen.generate()
        assert not stix2generator.test.utils.has_dangling_references(graph)
        assert stix2generator.test.utils.is_connected(graph)


def _objects_of_type(graph, type_):
    for obj in graph.values():
        if obj["type"] == type_:
            yield obj


def _object_pairs_of_types(graph, type1, type2):
    for obj1 in _objects_of_type(graph, type1):
        for obj2 in _objects_of_type(graph, type2):
            if obj1 is not obj2:
                yield obj1, obj2


def _constraints_enforced(graph):
    """
    Check if all applicable constraints have been enforced in the given graph.

    :return: True if all applicable constraints are enforced; False if not
    """
    for constraint in stix2generator.generation.reference_graph_generator\
            ._INVERSE_PROPERTIES:
        for obj1, obj2 in _object_pairs_of_types(
            graph, constraint.object_type1, constraint.object_type2
        ):
            if (
                constraint.is_applicable(obj1, constraint.prop_name1, obj2)
                and not constraint.holds(obj1, constraint.prop_name1, obj2)
            ) or (
                constraint.is_applicable(obj1, constraint.prop_name2, obj2)
                and not constraint.holds(obj1, constraint.prop_name2, obj2)
            ):
                result = False
                break

        else:
            continue

        break
    else:
        result = True

    return result


def _constraints_applicable(graph):
    """
    Check whether there are any applicable constraints on objects in the given
    graph.

    :param graph: The graph, as map from ID to object
    :return: True if any constraint applies to any objects; False if not
    """
    for constraint in stix2generator.generation.reference_graph_generator\
            ._INVERSE_PROPERTIES:
        for obj1, obj2 in _object_pairs_of_types(
            graph, constraint.object_type1, constraint.object_type2
        ):
            if constraint.is_applicable(
                obj1, constraint.prop_name1, obj2
            ) or constraint.is_applicable(
                obj1, constraint.prop_name2, obj2
            ):
                result = True
                break

        else:
            continue

        break
    else:
        result = False

    return result


def test_graph_enforce_inverse_properties(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    graph_gen_config = stix2generator.generation.reference_graph_generator\
        .Config(
            inverse_property_constraints="enforce"
        )
    ref_graph_gen = stix2generator.generation.reference_graph_generator\
        .ReferenceGraphGenerator(obj_gen, graph_gen_config)

    for _ in range(num_trials):
        # I feel like I should hard-code a STIX object type I know to contain
        # lots of reference properties and have applicable constraints, to have
        # a high likelihood that reference properties will be generated, the
        # graph will grow, and there will be some applicable constraints to
        # test.
        _, graph = ref_graph_gen.generate("network-traffic")
        assert _constraints_enforced(graph)


def test_graph_delete_inverse_properties(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    graph_gen_config = stix2generator.generation.reference_graph_generator\
        .Config(
            inverse_property_constraints="delete"
        )
    ref_graph_gen = stix2generator.generation.reference_graph_generator\
        .ReferenceGraphGenerator(obj_gen, graph_gen_config)

    for _ in range(num_trials):
        # I feel like I should hard-code a STIX object type I know to contain
        # lots of reference properties and have applicable constraints, to have
        # a high likelihood that reference properties will be generated, the
        # graph will grow, and there will be some applicable constraints to
        # test.
        _, graph = ref_graph_gen.generate("network-traffic")
        assert not _constraints_applicable(graph)


# Nothing to test for inverse_property_constraints=ignore.  In that case,
# anything goes.


def test_preexisting_objects(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    ref_graph_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(obj_gen, stix_version="2.1")

    for _ in range(num_trials):
        _, graph1 = ref_graph_gen.generate()

        _, graph2 = ref_graph_gen.generate(preexisting_objects=graph1)

        # just ensure graph2 absorbed graph1.  Anything else we can test?
        assert all(id_ in graph2 for id_ in graph1)

        # ensure all objects got parsed ok
        assert all(
            isinstance(obj, stix2.base._STIXBase)
            for obj in graph2.values()
        )


def test_stix2_parsing(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    ref_graph_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(obj_gen, stix_version="2.1")

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

        _, graph2 = ref_graph_gen.generate(preexisting_objects=graph1)

        # ensure graph2 absorbed graph1
        assert graph1.keys() <= graph2.keys()

        # ensure our preexisting identity is still a dict, but other objects
        # were parsed.
        for id_, obj in graph2.items():
            if id_ == identity["id"]:
                assert isinstance(obj, dict)
            else:
                assert isinstance(obj, stix2.base._STIXBase)


def test_not_parsing(num_trials):
    obj_gen_config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )
    obj_gen = stix2generator.create_object_generator(obj_gen_config)

    ref_graph_config = stix2generator.generation.reference_graph_generator \
        .Config(
            parse=False
        )
    ref_graph_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(obj_gen, ref_graph_config, stix_version="2.1")

    identity = stix2.v21.Identity(
        name="Alice"
    )

    for _ in range(num_trials):
        graph1 = {
            identity.id: identity
        }

        _, graph2 = ref_graph_gen.generate(preexisting_objects=graph1)

        # ensure graph2 absorbed graph1
        assert graph1.keys() <= graph2.keys()

        # Ensure the only parsed object is our original identity.
        for id_, obj in graph2.items():
            if id_ == identity.id:
                assert isinstance(obj, stix2.v21.Identity)

            else:
                assert isinstance(obj, dict)


def test_ref_gen_with_custom():
    """
    Set up a reference graph generator with an object generator with stuff
    you would not get by default via
    stix2generator.create_object_generator(...).  Reference graph generator
    creates a derivative "halt" generator, and we need to ensure that the
    latter inherits the same config as the original object generator, including
    registry and semantics providers.
    """
    class TestSemantics(stix2generator.generation.semantics.SemanticsProvider):
        def get_semantics(self):
            return ["testxyz"]

        def testxyz(self, spec, generator, constraint):
            return "test"

    custom_registry = {
        # A self-referential type, to cause simple reference chains
        "test-ref-type": {
            "type": "object",
            "optional": ["obj_ref"],
            "properties": {
                "id": {
                    "type": "string",
                    "semantics": "stix-id",
                    "stix-type": "test-ref-type"
                },
                "type": "test-ref-type",
                "test_prop": {
                    "type": "string",
                    "semantics": "testxyz"
                },
                "obj_ref": {
                    "type": "string",
                    "semantics": "stix-id",
                    "stix-type": "test-ref-type"
                }
            }
        }
    }

    @stix2.CustomObject("test-ref-type", [])
    class TestRefType:
        # This class won't be used since we'll turn the parse setting off; but
        # we need a registration so test-ref-type is seen as a generatable
        # type.  So we can leave it empty.
        pass

    semantics_providers = [
        TestSemantics(),
        stix2generator.generation.semantics.STIXSemantics()
    ]

    obj_gen_config = stix2generator.generation.object_generator.Config(
        optional_property_probability=1,
        minimize_ref_properties=False
    )

    obj_gen = stix2generator.generation.object_generator.ObjectGenerator(
        custom_registry, semantics_providers, obj_gen_config
    )

    ref_gen_config = stix2generator.generation.reference_graph_generator \
        .Config(
            graph_type="TREE",
            parse=False
        )

    ref_gen = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(
            obj_gen, ref_gen_config
        )

    _, graph = ref_gen.generate()

    for obj in graph.values():
        # Ensure our semantics provider was invoked properly for all objects
        assert obj["test_prop"] == "test"

        # Ensure no dangling references
        obj_ref = obj.get("obj_ref")
        if obj_ref is not None:
            assert obj_ref in graph

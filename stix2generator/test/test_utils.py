# Unit tests for the (top-level) utils module.
import pytest
import stix2.utils

import stix2generator.utils


@pytest.fixture(scope="module")
def object_generator21():
    """
    Create a default-configured object generator for STIX 2.1.
    """
    gen = stix2generator.create_object_generator(stix_version="2.1")
    return gen


@pytest.mark.parametrize(
    "obj, findings", [
        ({"type": "foo", "a_ref": 1, "b_ref": 2, "c": 3}, {("a_ref", 1), ("b_ref", 2)}),
        ({"type": "foo", "a_refs": [1, 2], "b_ref": 3, "c": 4}, {("a_refs", 1), ("a_refs", 2), ("b_ref", 3)}),
        ({"type": "foo", "a": {"b": {"c_ref": 1}}}, {("c_ref", 1)})
    ]
)
def test_find_references(obj, findings):
    for ref_prop, ref_id in stix2generator.utils.find_references(obj):
        assert (ref_prop, ref_id) in findings


@pytest.mark.parametrize(
    "obj", [
        {"type": "foo", "a_ref": 1, "b_ref": 1, "c": 1},
        {"type": "foo", "a_refs": [1, 1], "b_ref": 1, "c": 1},
        {"type": "foo", "a": {"b": {"c_ref": 1}}}
    ]
)
def test_find_references_assignable(obj):
    for parent, key, ref_id, _ in stix2generator.utils\
            .find_references_assignable(obj):
        assert ref_id == 1
        # just change all 1's to 2's
        parent[key] = 2

    for _, ref_id in stix2generator.utils.find_references(obj):
        assert ref_id == 2


@pytest.mark.parametrize(
    "constraints", [
        (("identity",)),
        (("identity", "location")),
        ((stix2.utils.STIXTypeClass.SDO, "url")),
        (("campaign", stix2.utils.STIXTypeClass.SCO)),
        ((
                stix2.utils.STIXTypeClass.SDO,
                stix2.utils.STIXTypeClass.SCO
        )),
    ]
)
def test_random_generatable_stix_type(
    num_trials, object_generator21, constraints
):
    for _ in range(num_trials):
        type_ = stix2generator.utils.random_generatable_stix_type(
            object_generator21, *constraints, stix_version="2.1"
        )

        assert stix2.utils.is_stix_type(
            type_, "2.1", *constraints
        )

        # try to generate an object to see if there is an error
        object_generator21.generate(type_)


@pytest.mark.parametrize(
    "constraints", [
        (("foo", "bar")),
        (())
    ]
)
def test_random_generatable_stix_type_not_found(
    num_trials, object_generator21, constraints
):
    for _ in range(num_trials):
        type_ = stix2generator.utils.random_generatable_stix_type(
            object_generator21, *constraints, stix_version="2.1"
        )

        assert type_ is None

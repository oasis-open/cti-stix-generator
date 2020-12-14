# Unit tests for the (top-level) utils module.
import pytest

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
    "obj_or_type, stix_version, expected", [
        ("identity", "2.1", True),
        ("identity", "2.0", True),
        ("ipv4-addr", "2.1", False),
        ("ipv4-addr", "2.0", False),
        ("bundle", "2.1", False),
        ("bundle", "2.0", False),
        ("marking-definition", "2.1", False),
        ("marking-definition", "2.0", False),
        ("foobar", "2.1", False),
        ("foobar", "2.0", False),
        ("relationship", "2.1", False),
        ("relationship", "2.0", False),
        ({"type": "malware-analysis", "foo": 1}, "2.1", True),
        ({"type": "malware-analysis", "foo": 1}, "2.0", False)
    ]
)
def test_is_sdo(obj_or_type, stix_version, expected):
    assert stix2generator.utils.is_sdo(obj_or_type, stix_version) is expected
    assert stix2generator.utils.is_stix_type(
        obj_or_type, stix2generator.utils.STIXTypeClass.SDO,
        stix_version=stix_version
    ) is expected


@pytest.mark.parametrize(
    "obj_or_type, stix_version, expected", [
        ("identity", "2.1", False),
        ("identity", "2.0", False),
        ("ipv4-addr", "2.1", True),
        ("ipv4-addr", "2.0", True),
        ("bundle", "2.1", False),
        ("bundle", "2.0", False),
        ("marking-definition", "2.1", False),
        ("marking-definition", "2.0", False),
        ("foobar", "2.1", False),
        ("foobar", "2.0", False),
        ("relationship", "2.1", False),
        ("relationship", "2.0", False),
        ({"type": "mutex", "foo": 1}, "2.1", True),
        ({"type": "mutex", "foo": 1}, "2.0", True)
    ]
)
def test_is_sco(obj_or_type, stix_version, expected):
    assert stix2generator.utils.is_sco(obj_or_type, stix_version) is expected
    assert stix2generator.utils.is_stix_type(
        obj_or_type, stix2generator.utils.STIXTypeClass.SCO,
        stix_version=stix_version
    ) is expected


@pytest.mark.parametrize(
    "obj_or_type, stix_version, expected", [
        ("identity", "2.1", False),
        ("identity", "2.0", False),
        ("ipv4-addr", "2.1", False),
        ("ipv4-addr", "2.0", False),
        ("bundle", "2.1", False),
        ("bundle", "2.0", False),
        ("marking-definition", "2.1", False),
        ("marking-definition", "2.0", False),
        ("foobar", "2.1", False),
        ("foobar", "2.0", False),
        ("relationship", "2.1", True),
        ("relationship", "2.0", True),
        ("sighting", "2.1", True),
        ("sighting", "2.0", True),
        ({"type": "mutex", "foo": 1}, "2.1", False),
        ({"type": "mutex", "foo": 1}, "2.0", False)
    ]
)
def test_is_sro(obj_or_type, stix_version, expected):
    assert stix2generator.utils.is_sro(obj_or_type, stix_version) is expected
    assert stix2generator.utils.is_stix_type(
        obj_or_type, stix2generator.utils.STIXTypeClass.SRO,
        stix_version=stix_version
    ) is expected


@pytest.mark.parametrize(
    "obj_or_type, stix_version, expected", [
        ("identity", "2.1", True),
        ("identity", "2.0", True),
        ("ipv4-addr", "2.1", True),
        ("ipv4-addr", "2.0", True),
        ("bundle", "2.1", True),
        ("bundle", "2.0", True),
        ("marking-definition", "2.1", True),
        ("marking-definition", "2.0", True),
        ("foobar", "2.1", False),
        ("foobar", "2.0", False),
        ("relationship", "2.1", True),
        ("relationship", "2.0", True),
        ({"type": "mutex", "foo": 1}, "2.1", True),
        ({"type": "mutex", "foo": 1}, "2.0", True)
    ]
)
def test_is_object(obj_or_type, stix_version, expected):
    assert stix2generator.utils.is_object(obj_or_type, stix_version) is expected


@pytest.mark.parametrize(
    "obj_or_type, constraints, expected", [
        (
            "identity", (
                stix2generator.utils.STIXTypeClass.SDO,
                stix2generator.utils.STIXTypeClass.SCO
            ),
            True
        ),
        (
            "identity", (
                "identity",
                stix2generator.utils.STIXTypeClass.SCO
            ),
            True
        ),
        (
            "identity", (
                stix2generator.utils.STIXTypeClass.SDO,
                "malware"
            ),
            True
        ),
        (
            "identity", (
                "location",
                "identity"
            ),
            True
        ),
        (
            "identity", (
                "location",
                "malware"
            ),
            False
        ),
        (
            "foobar", (
                "location",
                "malware"
            ),
            False
        ),
    ]
)
def test_is_stix_type(obj_or_type, constraints, expected):
    assert stix2generator.utils.is_stix_type(
        obj_or_type, *constraints, stix_version="2.1"
    ) is expected


@pytest.mark.parametrize(
    "constraints", [
        (("identity",)),
        (("identity", "location")),
        ((stix2generator.utils.STIXTypeClass.SDO, "url")),
        (("campaign", stix2generator.utils.STIXTypeClass.SCO)),
        ((
                stix2generator.utils.STIXTypeClass.SDO,
                stix2generator.utils.STIXTypeClass.SCO
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

        assert stix2generator.utils.is_stix_type(
            type_, *constraints, stix_version="2.1"
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

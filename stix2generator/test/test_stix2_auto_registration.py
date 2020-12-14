import pytest
import stix2

try:
    import stix2.parsing as mappings
except ImportError:
    import stix2.core as mappings

import stix2.exceptions
import stix2generator
import stix2generator.exceptions
from stix2generator.stixcustom import (
    stix2_register_custom, stix2_auto_register_all_custom
)


# Lazy-initialize.  Will hold a map from stix vid (e.g. "v20", "v21", etc)
# to a set of names.  So we have a separate set of names for each STIX
# version.
_STIX2_BUILTIN_SDO_NAMES = None


@pytest.fixture
def cleanup_stix2():
    """
    Auto-registration affects a global table within stix2.  So testing it can
    affect all subsequent tests unless the changes are undone after each test.
    This fixture doesn't produce anything; just use it for those unit tests
    which register anything custom, and it will undo the registration
    afterword.
    """

    global _STIX2_BUILTIN_SDO_NAMES

    # Store current SDO class entries upon first use.  This will allow us
    # to recognize from now on, if any entries are "custom".
    if _STIX2_BUILTIN_SDO_NAMES is None:
        _STIX2_BUILTIN_SDO_NAMES = {
            stix_vid: set(entries["objects"])
            for stix_vid, entries in mappings.STIX2_OBJ_MAPS.items()
        }

    yield

    for stix_vid, entries in mappings.STIX2_OBJ_MAPS.items():
        to_delete = [  # avoid modify-as-you-iterate
            obj_type for obj_type in entries["objects"]
            if obj_type not in _STIX2_BUILTIN_SDO_NAMES[stix_vid]
        ]

        for custom_type in to_delete:
            # print("Cleaning for", stix_vid, ":", custom_type)
            del entries["objects"][custom_type]


def test_const_object_spec_all_types(cleanup_stix2):
    spec = {
        "const": {
            "type": "my-type",
            "int": 1,
            "number": 0.5,
            "boolean": False,
            "string": "hello, world",
            "array": [1, 2, 3],
            "object": {
                "subprop1": 1,
                "subprop2": "two"
            }
        }
    }

    stix2_register_custom(spec, "my-type", "2.1")

    # now it should be able to parse our object
    obj = stix2.parse(spec["const"], version="2.1")

    assert obj["type"] == "my-type"
    assert obj["int"] == 1
    assert obj["number"] == 0.5
    assert obj["boolean"] is False
    assert obj["string"] == "hello, world"
    assert obj["array"] == [1, 2, 3]
    assert obj["object"] == {"subprop1": 1, "subprop2": "two"}


def test_nonconst_object_spec_all_types(cleanup_stix2):
    spec = {
        "type": "object",
        "properties": {
            "type": "my-type",
            "int": {"type": "integer"},
            "number": {"type": "number"},
            "boolean": {"type": "boolean"},
            "string": {"type": "string"},
            "array": {"type": "array", "items": {"type": "integer"}},
            "object": {
                "type": "object",
                "properties": {
                    "subprop1": {"type": "integer"},
                    "subprop2": {"type": "string"}
                }
            }
        }
    }

    stix2_register_custom(spec, "my-type", "2.1")

    gen = stix2generator.create_object_generator()
    random_dict = gen.generate_from_spec(spec)
    stix_obj = stix2.parse(random_dict, version="2.1")

    # Make sure all props from the dict came through in the stix2 object
    for prop, value in random_dict.items():
        assert stix_obj[prop] == value


def test_specs_dict(cleanup_stix2):
    specs = {
        "Custom1": {
            "const": {
                "type": "custom1",
                "name": "alice"
            }
        },
        "Custom2": {
            "const": {
                "type": "custom2",
                "name": "bob"
            }
        },
        "somehelper": {
            "const": {
                "type": "somehelper",
                "name": "carol"
            }
        }
    }

    stix2_auto_register_all_custom(specs, "2.1")

    # Note that the specs are used to detect property types; exact values
    # are not enforced, nor even whether each property is present at all.
    custom1 = stix2.parse({"type": "custom1", "name": "carol"}, version="2.1")
    custom2 = stix2.parse({"type": "custom2"}, version="2.1")

    assert custom1["name"] == "carol"
    assert "name" not in custom2

    # "somehelper" should not be recognized as an SDO spec since it starts
    # with lowercase, so it should be skipped for auto-registration.  So the
    # following should fail.
    with pytest.raises(stix2.exceptions.ParseError):
        stix2.parse({"type": "somehelper"})


def test_non_object_spec_error():
    spec = [1, 2, 3]

    # We're registering a custom STIX object, so the spec needs to be for an
    # object!
    with pytest.raises(stix2generator.exceptions.IllegalSTIXObjectSpecType):
        stix2_register_custom(spec, "foo", "2.1")


def test_empty_list_error():
    spec = {
        "type": "object",
        "properties": {
            "emptylist": []
        }
    }

    # can't infer list element type from an empty list
    with pytest.raises(stix2generator.exceptions.EmptyListError):
        stix2_register_custom(spec, "foo", "2.1")


def test_heterogenous_list_error():
    spec = {
        "type": "object",
        "properties": {
            "heterolist": [1, "foo", True]
        }
    }

    # can't infer list element type from a heterogenous list
    with pytest.raises(stix2generator.exceptions.HeterogenousListError):
        stix2_register_custom(spec, "foo", "2.1")


def test_prop_type_error():
    spec = {
        "const": {
            "nullprop": None
        }
    }

    with pytest.raises(stix2generator.exceptions.IllegalSTIXObjectPropertyType):
        stix2_register_custom(spec, "null", "2.1")


def test_stix2_object_result(cleanup_stix2):
    spec = {
        "Foobar": {
            "type": "object",
            "import": "common-properties",
            "required": ["id", "some-property", "type"],
            "properties": {
                "type": "x-foobar",
                "id": {
                    "type": "string",
                    "semantics": "stix-id",
                    "stix-type": "x-foobar"
                },
                "some-property": {
                    "type": "string",
                    "semantics": "word"
                }
            }
        }
    }

    stix2_register_custom(spec['Foobar'], "x-foobar", "2.1")
    processor = stix2generator.create_default_language_processor(
        extra_specs=spec, stix_version="2.1"
    )
    obj = processor.build_graph("Foobar.")[0]

    assert isinstance(obj, stix2.base._STIXBase)

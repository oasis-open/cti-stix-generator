import pytest

import stix2generator.exceptions


def test_object(object_generator):
    value = object_generator.generate_from_spec({
        "type": "object",
        "properties": {
            "a": 1,
            "b": 2
        }
    })

    assert isinstance(value, dict)
    assert "a" in value
    assert "b" in value
    assert value == {"a": 1, "b": 2}


def test_object_optional_props(object_generator, num_trials):
    for _ in range(num_trials):
        # test with "optional"
        value = object_generator.generate_from_spec({
            "type": "object",
            "optional": ["b"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        assert "a" in value
        assert all(prop_name in ("a", "b") for prop_name in value)

        # test with "required"
        value = object_generator.generate_from_spec({
            "type": "object",
            "required": ["a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        assert "a" in value
        assert all(prop_name in ("a", "b") for prop_name in value)


def test_object_presence_coconstraint_one_required(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"]
            },
            "required": ["group-a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        # exactly one of "a" and "b" must be there
        assert "a" in value or "b" in value
        assert not ("a" in value and "b" in value)


def test_object_presence_coconstraint_one_optional(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"]
            },
            "optional": ["group-a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        # only "a", only "b", or no properties at all should be there
        assert ("a" in value and "b" not in value) or \
               ("a" not in value and "b" in value) or \
               not value


def test_object_presence_coconstraint_at_least_one_required(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "at-least-one": ["group-a"]
            },
            "required": ["group-a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        # one or both of "a" and "b" must be there
        assert "a" in value or "b" in value


def test_object_presence_coconstraint_at_least_one_optional(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "at-least-one": ["group-a"]
            },
            "optional": ["group-a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        # silly case: both, either, or neither of "a" and "b" can be present,
        # same as making them all optional.  Shouldn't write a spec like this,
        # it's overly complicated.
        assert all(prop_name in ("a", "b") for prop_name in value)


def test_object_presence_coconstraint_all_required(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "all": ["group-a"]
            },
            "required": ["group-a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        # silly case: all properties in group-a are required, same as if they
        # were all individually declared to be required.  Shouldn't write a
        # spec like this, it's overly complicated.
        assert "a" in value and "b" in value


def test_object_presence_coconstraint_all_optional(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "all": ["group-a"]
            },
            "optional": ["group-a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        # both or neither of "a" and "b" must be there.
        assert ("a" in value and "b" in value) or not value


def test_object_presence_coconstraint_dependencies_props(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "dependencies": {
                    "a": ["b", "c"]
                }
            },
            "optional": ["a", "b", "c"],
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })

        # If "a" is present, "b" and "c" must be present.  If "a" is not
        # present, "b" and "c" may or may not be present (since they're
        # declared optional).
        if "a" in value:
            assert "b" in value and "c" in value
        else:
            assert all(prop_name in ("b", "c") for prop_name in value)


def test_object_presence_coconstraint_dependencies_group_key(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"],
                "dependencies": {
                    "group-a": ["c"]
                }
            },
            "optional": ["group-a", "c"],
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })

        # If "a" or "b" are present, then "c" must also be present.  If neither
        # "a" nor "b" are present, "c" may or may not be present (since it's
        # declared optional).
        if "a" in value or "b" in value:
            assert "c" in value
        else:
            assert "c" in value or not value


def test_object_presence_coconstraint_dependencies_group_value(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"],
                "dependencies": {
                    "c": ["group-a"]
                }
            },
            "optional": ["group-a", "c"],
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })

        # If "c" is present, then exactly one of "a" or "b" must be present.
        # If "c" is not present, then exactly one or neither of "a" and "b"
        # must be present (since group-a is declared optional).
        if "c" in value:
            assert "a" in value or "b" in value
        else:
            assert "a" in value or "b" in value or not value


def test_object_presence_coconstraint_dependencies_group_key_and_value(
    object_generator, num_trials
):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"],
                    "group-b": ["c", "d"]
                },
                "one": ["group-a"],
                "all": ["group-b"],
                "dependencies": {
                    "group-a": ["group-b"]
                }
            },
            "optional": ["group-a", "group-b"],
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3,
                "d": 4
            }
        })

        # If exactly one of "a" or "b" is present, then both of "c" and "d"
        # must be present.  If neither "a" nor "b" is present, then neither or
        # both of "c" and "d" may be present.
        if "a" in value or "b" in value:
            assert "c" in value and "d" in value
        else:
            assert ("c" in value and "d" in value) or not value


def test_object_presence_coconstraint_errors1(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    # refer to undefined property in group
                    "group-a": ["a", "c"]
                },
                "one": ["group-a"]
            },
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors2(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                # refer to undefined group in co-constraint
                "one": ["group-b"]
            },
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors3(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "dependencies": {
                    # refer to undefined property as value
                    "a": ["b", "c"]
                }
            },
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors4(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "dependencies": {
                    # refer to undefined property as key
                    "c": ["a", "b"]
                }
            },
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors5(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"],
                "dependencies": {
                    # refer to undefined group as value
                    "c": ["group-b"]
                }
            },
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })


def test_object_presence_coconstraint_errors6(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"],
                "dependencies": {
                    # refer to undefined group as key
                    "group-b": ["c"]
                }
            },
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })


def test_object_presence_coconstraint_errors7(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                }
                # group-a is missing its constraint
            },
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors8(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"],
                    # groups can't overlap
                    "group-b": ["b", "c"]
                },
                "one": ["group-a", "group-b"]
            },
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })


def test_object_presence_coconstraint_errors9(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"],
                "dependencies": {
                    # can't directly refer to grouped properties
                    "a": ["group-a"]
                }
            },
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors10(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group-a": ["a", "b"]
                },
                "one": ["group-a"]
            },
            # can't directly refer to grouped properties
            "required": ["a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_presence_coconstraint_errors11(object_generator):
    with pytest.raises(stix2generator.exceptions.PresenceCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    # can't name a group the same as a property
                    "a": ["b", "c"]
                },
                "one": ["a"]
            },
            "properties": {
                "a": 1,
                "b": 2,
                "c": 3
            }
        })


def test_object_value_coconstraint(object_generator):

    object_generator.generate_from_spec({
        "type": "object",
        # Value co-constraints currently only used in certain semantics;
        # they will be ignored in this spec.  Just check for errors.
        "value-coconstraints": [
            "a < b",
            "a <= b",
            "a > b",
            "a >= b",
            "a = b",
            "a != b"
        ],
        "properties": {
            "a": 1,
            "b": 2
        }
    })


def test_object_value_coconstraint_bad_operator(object_generator):
    with pytest.raises(stix2generator.exceptions.ValueCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            # invalid operator
            "value-coconstraints": ["a $ b"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_value_coconstraint_bad_property(object_generator):
    with pytest.raises(stix2generator.exceptions.ValueCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            # undefined property name
            "value-coconstraints": ["a = x"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })


def test_object_value_coconstraint_self_relation(object_generator):
    with pytest.raises(stix2generator.exceptions.ValueCoconstraintError):
        object_generator.generate_from_spec({
            "type": "object",
            # can't relate a prop to itself
            "value-coconstraints": ["a = a"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

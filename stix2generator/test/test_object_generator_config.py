import stix2generator.generation.object_generator


def test_config_string(num_trials):
    config = stix2generator.generation.object_generator.Config(
        string_length_min=2,
        string_length_max=6,
        string_chars="abc"
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "string"
        })

        assert 2 <= len(value) <= 6
        assert all(c in "abc" for c in value)


def test_config_integer(num_trials):
    config = stix2generator.generation.object_generator.Config(
        number_min=2,
        number_max=6,
        is_number_max_exclusive=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "integer"
        })

        assert isinstance(value, int)
        assert 2 <= value < 6


def test_config_number(num_trials):
    config = stix2generator.generation.object_generator.Config(
        number_min=2.7,
        is_number_min_exclusive=True,
        number_max=6.2
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "number"
        })

        assert isinstance(value, float)
        assert 2.7 < value <= 6.2


def test_config_array_length(num_trials):
    config = stix2generator.generation.object_generator.Config(
        array_length_min=2,
        array_length_max=6
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "array",
            "items": 1
        })

        assert isinstance(value, list)
        assert 2 <= len(value) <= 6


def test_config_optional_property_probability_0(num_trials):
    config = stix2generator.generation.object_generator.Config(
        optional_property_probability=0
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "optional": ["a", "b"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        assert isinstance(value, dict)
        assert not value  # all props optional, none should be included


def test_config_optional_property_probability_1(num_trials):
    config = stix2generator.generation.object_generator.Config(
        optional_property_probability=1
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "optional": ["a", "b"],
            "properties": {
                "a": 1,
                "b": 2
            }
        })

        assert isinstance(value, dict)
        assert len(value) == 2  # all props optional, but all should be included


def test_config_minimize_ref_properties1(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "required": [],  # all properties optional
            "properties:": {
                "a_ref": 1,
                "b": 2
            }
        })

        # a_ref optional, so it is always omitted
        assert "a_ref" not in value
        assert "b" in value or not value


def test_config_minimize_ref_properties2(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "required": ["a_ref"],
            "properties": {
                "a_ref": 1,
                "b": 2
            }
        })

        # a_ref required, so it is always present, even though we are
        # trying to minimize ref properties.
        assert "a_ref" in value


def test_config_minimize_ref_properties3(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b_ref"]
                },
                "one": ["group"]
            },
            "required": [],
            "properties": {
                "a_ref": 1,
                "b_ref": 2,
                "c": 3
            }
        })

        # presence co-constraint group "group" can't be satisfied with non-ref
        # properties, and it is optional, so the whole group is always omitted
        assert "a_ref" not in value and "b_ref" not in value


def test_config_minimize_ref_properties4(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b_ref"]
                },
                "one": ["group"]
            },
            "required": ["group"],
            "properties": {
                "a_ref": 1,
                "b_ref": 2,
                "c": 3
            }
        })

        # presence co-constraint group "group" can't be satisfied with non-ref
        # properties, but it's required, so one of the ref properties must be
        # there.
        assert "a_ref" in value or "b_ref" in value


def test_config_minimize_ref_properties5(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b_ref"]
                },
                "at-least-one": ["group"]
            },
            "required": ["group"],
            "properties": {
                "a_ref": 1,
                "b_ref": 2,
                "c": 3
            }
        })

        # presence co-constraint group "group" can't be satisfied with non-ref
        # properties, but it's required.  In this case, the constraint says
        # we can choose more than one from the group, but when minimizing
        # reference properties, we never choose more than one.  In this
        # situation, "at-least-one" behaves exactly the same as "one".
        assert "a_ref" in value or "b_ref" in value
        assert "a_ref" not in value or "b_ref" not in value


def test_config_minimize_ref_properties6(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b_ref"]
                },
                "all": ["group"]
            },
            "required": ["group"],
            "properties": {
                "a_ref": 1,
                "b_ref": 2,
                "c": 3
            }
        })

        # presence co-constraint group "group" can't be satisfied with non-ref
        # properties, but it's required.  Since it's an "all" group, both ref
        # properties must always be present
        assert "a_ref" in value and "b_ref" in value


def test_config_minimize_ref_properties7(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b"]
                },
                "one": ["group"]
            },
            "required": ["group"],
            "properties": {
                "a_ref": 1,
                "b": 2,
                "c": 3
            }
        })

        # presence co-constraint group "group" can be satisfied with non-ref
        # properties, and it is required, so the non-ref property must always
        # be chosen as the satisfying property.  So "a_ref" will never appear
        # and "b" will always appear.
        assert "a_ref" not in value and "b" in value


def test_config_minimize_ref_properties8(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b"]
                },
                "at-least-one": ["group"]
            },
            "required": ["group"],
            "properties": {
                "a_ref": 1,
                "b": 2,
                "c": 3
            }
        })

        # Same as prev test, but with at-least-one co-constraint:
        # presence co-constraint group "group" can be satisfied with non-ref
        # properties, and it is required, so the non-ref property must always
        # be chosen as the satisfying property.  So "a_ref" will never appear
        # and "b" will always appear.
        assert "a_ref" not in value and "b" in value


def test_config_minimize_ref_properties9(num_trials):
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=True,
        optional_property_probability=1
    )
    generator = stix2generator.generation.object_generator.ObjectGenerator(
        config=config
    )

    for _ in range(num_trials):
        value = generator.generate_from_spec({
            "type": "object",
            "presence-coconstraints": {
                "property-groups": {
                    "group": ["a_ref", "b_refs"]
                },
                "all": ["group"]
            },
            "required": [],
            "properties": {
                "a_ref": 1,
                "b_refs": 2,
                "c": 3
            }
        })

        # There is a conflict in the settings: optional_property_probability=1
        # means always include optional properties, and group "group" is
        # optional.  But it can't be satisfied with non-ref properties, so
        # minimize_ref_properties takes priority and the group is always
        # omitted.
        assert "a_ref" not in value and "b_refs" not in value

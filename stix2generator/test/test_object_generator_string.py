import pytest

import stix2generator.exceptions


def test_string(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "string",
            "minLength": 1,
            "maxLength": 5
        })

        assert 1 <= len(value) <= 5
        assert isinstance(value, str)


def test_string_missing_length_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "minLength": 1
        })

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "maxLength": 5
        })


def test_string_inverted_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "minLength": 5,
            "maxLength": 1
        })


def test_string_negative_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "minLength": 1,
            "maxLength": -5
        })

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "minLength": -1,
            "maxLength": 5
        })

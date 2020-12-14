import pytest

import stix2generator.exceptions


def test_array(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5
            }
        })

        assert isinstance(value, list)
        assert 1 <= len(value) <= 5
        assert all(isinstance(elt, int) for elt in value)
        assert all(1 <= elt <= 5 for elt in value)


def test_array_inverted_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "array",
            "minItems": 5,
            "maxItems": 1,
            "items": 1
        })


def test_array_negative_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "array",
            "minItems": -1,
            "maxItems": 5,
            "items": 1
        })

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "array",
            "minItems": 1,
            "maxItems": -5,
            "items": 1
        })

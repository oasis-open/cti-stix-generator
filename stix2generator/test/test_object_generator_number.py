import pytest

import stix2generator.exceptions


def test_number_closed(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "number",
            "minimum": 0,
            "maximum": 1
        })

        assert 0 <= value <= 1
        assert isinstance(value, float)


def test_number_open(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "number",
            "exclusiveMinimum": 0,
            "exclusiveMaximum": 1
        })

        assert 0 < value < 1


def test_number_half_open_lower(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "number",
            "exclusiveMinimum": 0,
            "maximum": 1
        })

        assert 0 < value <= 1


def test_number_half_open_upper(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "number",
            "minimum": 0,
            "exclusiveMaximum": 1
        })

        assert 0 <= value < 1


def test_number_very_large(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        # floats have a different, smaller range than ints.  This upper bound
        # is outside the range of floats.
        object_generator.generate_from_spec({
            "type": "number",
            "minimum": 0,
            "maximum": 10**10000
        })


def test_number_inverted_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "number",
            "minimum": 1,
            "maximum": 0
        })

import pytest

import stix2generator.exceptions


def test_integer_closed(object_generator, num_trials):

    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "minimum": -1,
            "maximum": 1
        })

        assert -1 <= value <= 1


def test_integer_open(object_generator, num_trials):

    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "exclusiveMinimum": -1,
            "exclusiveMaximum": 1
        })

        assert value == 0


def test_integer_half_open_lower(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "exclusiveMinimum": -1,
            "maximum": 1
        })

        assert -1 < value <= 1


def test_integer_half_open_upper(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "minimum": -1,
            "exclusiveMaximum": 1
        })

        assert -1 <= value < 1


def test_integer_float_bounds(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "minimum": -1.5,
            "maximum": 1.5
        })

        assert -1 <= value <= 1
        assert isinstance(value, int)


def test_integer_bounds_single_int(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "minimum": 1,
            "maximum": 1
        })

        assert value == 1


def test_integer_float_bounds_single_int(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "minimum": 0.5,
            "maximum": 1.5
        })

        assert value == 1
        assert isinstance(value, int)


def test_integer_empty_interval(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "integer",
            "exclusiveMinimum": 1,
            "exclusiveMaximum": 1
        })


def test_integer_empty_interval_float_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "integer",
            "minimum": 1.1,
            "maximum": 1.9
        })


def test_integer_very_large(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "minimum": 10**9999,
            "maximum": 10**10000
        })

        assert 10**9999 <= value <= 10**10000


def test_integer_inverted_bounds(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "integer",
            "minimum": 1,
            "maximum": -1
        })

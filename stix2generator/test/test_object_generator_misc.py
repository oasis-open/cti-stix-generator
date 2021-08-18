import pytest

import stix2generator.exceptions
import stix2generator.generation.object_generator


def test_one_of(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "integer",
            "oneOf": [1, 2]
        })

        assert value == 1 or value == 2


def test_one_of_with_weights(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "string",
            "oneOf": {
                "choices": [
                    "2021-01-01T00:00:00.000Z",
                    "9999-01-01T00:00:00.000Z",
                    "1999-01-01T00:00:00.000Z"
                ],
                "weights": [60, 40, 0]
            }
        })

        assert value in ("9999-01-01T00:00:00.000Z", "2021-01-01T00:00:00.000Z")


def test_one_of_invalid_weights(object_generator):

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "oneOf": {
                "choices": [1, 2, 3],
                # negative weights not allowed
                "weights": [-1, 2, 3]
            }
        })

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "oneOf": {
                "choices": [1, 2, 3],
                # all zero weights not allowed
                "weights": [0, 0, 0]
            }
        })

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "oneOf": {
                "choices": [1, 2, 3],
                # Different number of weights and choices is not allowed
                "weights": [1, 2, 3, 4, 5]
            }
        })

    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "type": "string",
            "oneOf": {
                # Must have at least one choice
                "choices": [],
                "weights": []
            }
        })


def test_ref():

    registry = {
        "spec1": {
            "type": "integer",
            "ref": "spec2"
        },
        "spec2": 1
    }

    generator = stix2generator.generation.object_generator.ObjectGenerator(
        registry
    )

    value = generator.generate("spec1")

    assert value == 1


def test_ref_type_error():

    with pytest.raises(stix2generator.exceptions.TypeMismatchError):
        registry = {
            "spec1": {
                "type": "string",
                # refs to an int spec instead of a string!
                "ref": "spec2"
            },
            "spec2": 1
        }

        generator = stix2generator.generation.object_generator.ObjectGenerator(
            registry
        )

        generator.generate("spec1")


def test_ref_loop_error():

    with pytest.raises(
        stix2generator.exceptions.CyclicSpecificationReferenceError
    ):
        registry = {
            "spec1": {
                "type": "string",
                "ref": "spec2"
            },
            "spec2": {
                "type": "string",
                "ref": "spec1"
            }
        }

        generator = stix2generator.generation.object_generator.ObjectGenerator(
            registry
        )

        generator.generate("spec1")


def test_unrecognized_spec_error(object_generator):
    with pytest.raises(stix2generator.exceptions.SpecificationNotFoundError):
        object_generator.generate("foo")


def test_const_spec_1(object_generator):
    # Any non-dict spec generates itself
    value = object_generator.generate_from_spec(1)

    assert value == 1


def test_const_spec_2(object_generator):
    # A "const" property is another way to generate a constant value
    value = object_generator.generate_from_spec({
        "const": {
            "a": 1,
            "b": 2
        }
    })

    assert value == {"a": 1, "b": 2}


def test_const_bad_type_1(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        # const specs must be a JSON type
        object_generator.generate_from_spec(object())


def test_const_bad_type_2(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        # const specs must be a JSON type
        object_generator.generate_from_spec({
            "const": object()
        })


def test_bad_type_property(object_generator):
    with pytest.raises(stix2generator.exceptions.UnrecognizedJSONTypeError):
        object_generator.generate_from_spec({
            "type": "foo"
        })


def test_missing_type_property(object_generator):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        object_generator.generate_from_spec({
            "a": 1
        })

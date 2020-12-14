import datetime
import faker
import operator
import pytest
import uuid

import stix2generator.exceptions
import stix2generator.generation.constraints
import stix2generator.generation.object_generator
import stix2generator.generation.semantics


_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class DummySemantics(stix2generator.generation.semantics.SemanticsProvider):
    """Dummy simple semantics provider"""
    def get_semantics(self):
        return ["add"]

    def add(self, spec, generator, constraint):
        # Generate the sum of properties "a" and "b"
        return spec["a"] + spec["b"]


@pytest.fixture(scope="module")
def generator_dummy_semantics():
    test_provider = DummySemantics()

    return stix2generator.generation.object_generator.ObjectGenerator(
        semantic_providers=[test_provider]
    )


@pytest.fixture(scope="module")
def generator_stix_semantics():
    stix_provider = stix2generator.generation.semantics.STIXSemantics()

    return stix2generator.generation.object_generator.ObjectGenerator(
        semantic_providers=[stix_provider]
    )


@pytest.fixture(scope="module")
def generator_faker_semantics():
    faker_ = faker.Faker()
    faker_provider = stix2generator.generation.semantics.FakerSemantics(faker_)

    return stix2generator.generation.object_generator.ObjectGenerator(
        semantic_providers=[faker_provider]
    )


def test_semantics(generator_dummy_semantics):

    value = generator_dummy_semantics.generate_from_spec({
        "type": "integer",
        "semantics": "add",
        "a": 1,
        "b": 2
    })

    assert value == 3


def test_undefined_semantics(generator_dummy_semantics):
    with pytest.raises(stix2generator.exceptions.ObjectGenerationError):
        generator_dummy_semantics.generate_from_spec({
            "type": "integer",
            "semantics": "foo"
        })


def test_semantics_type_error(generator_dummy_semantics):
    with pytest.raises(
        stix2generator.exceptions.SemanticValueTypeMismatchError
    ):
        generator_dummy_semantics.generate_from_spec({
            "type": "string",
            "semantics": "add",
            "a": 1,
            "b": 2
        })


def test_stix_semantics_id(generator_stix_semantics, num_trials):
    for _ in range(num_trials):

        value = generator_stix_semantics.generate_from_spec({
            "type": "string",
            "semantics": "stix-id",
            "stix-type": "some-type"
        })

        dd_idx = value.index("--")
        assert value[:dd_idx] == "some-type"

        id_uuid = uuid.UUID(value[dd_idx+2:])
        assert id_uuid.variant == uuid.RFC_4122
        assert id_uuid.version == 4


def test_stix_semantics_timestamp(generator_stix_semantics, num_trials):
    for _ in range(num_trials):
        value = generator_stix_semantics.generate_from_spec({
            "type": "string",
            "semantics": "stix-timestamp"
        })

        # Just ensure the value parses as a timestamp
        datetime.datetime.strptime(value, _TIMESTAMP_FORMAT)


@pytest.mark.parametrize("gen_op,python_op", [
    ("<", operator.lt),
    ("<=", operator.le),
    ("=", operator.eq),
    ("!=", operator.ne),
    (">", operator.gt),
    (">=", operator.ge)
])
def test_stix_semantics_timestamp_constraint(
    generator_stix_semantics, num_trials, gen_op, python_op
):
    """
    Test value constraint satisfaction in the stix-timestamp semantics
    implementation.
    """
    constraint_ts_str = "2017-10-28T21:12:08Z"
    constraint_ts_dt = datetime.datetime.strptime(
        constraint_ts_str, _TIMESTAMP_FORMAT
    )
    constraint_obj = stix2generator.generation.constraints.ValueConstraint(
        gen_op, constraint_ts_str
    )

    for _ in range(num_trials):
        # Here, we just feed the constraint in directly.  This isn't how
        # the mechanism is likely to be used though.
        value = generator_stix_semantics.generate_from_spec(
            {
                "type": "string",
                "semantics": "stix-timestamp"
            },
            value_constraint=constraint_obj
        )

        gen_ts_dt = datetime.datetime.strptime(value, _TIMESTAMP_FORMAT)

        assert python_op(gen_ts_dt, constraint_ts_dt)


@pytest.mark.parametrize("gen_op,python_op", [
    ("<", operator.lt),
    ("<=", operator.le),
    ("=", operator.eq),
    ("!=", operator.ne),
    (">", operator.gt),
    (">=", operator.ge)
])
def test_stix_semantics_timestamp_coconstraint(
    generator_stix_semantics, num_trials, gen_op, python_op
):
    """
    Test value co-constraint satisfaction in the object generator.
    """
    for _ in range(num_trials):
        value = generator_stix_semantics.generate_from_spec({
            "type": "object",
            "value-coconstraints": [
                "ts1 {} ts2".format(gen_op)
            ],
            "properties": {
                "ts1": {
                    "type": "string",
                    "semantics": "stix-timestamp"
                },
                "ts2": {
                    "type": "string",
                    "semantics": "stix-timestamp"
                }
            }
        })

        ts1_dt = datetime.datetime.strptime(value["ts1"], _TIMESTAMP_FORMAT)
        ts2_dt = datetime.datetime.strptime(value["ts2"], _TIMESTAMP_FORMAT)

        assert python_op(ts1_dt, ts2_dt)


def test_faker_semantics(generator_faker_semantics, num_trials):
    for _ in range(num_trials):
        # just pick some random faker functions and test them...

        value = generator_faker_semantics.generate_from_spec({
            "type": "array",
            "semantics": "words",
            "nb": 3
        })

        assert all(isinstance(word, str) for word in value)
        assert len(value) == 3

        value = generator_faker_semantics.generate_from_spec({
            "type": "boolean",
            "semantics": "boolean"
        })

        assert value in (True, False)

        value = generator_faker_semantics.generate_from_spec({
            "type": "string",
            "semantics": "uuid4"
        })

        value_uuid = uuid.UUID(value)
        assert value_uuid.variant == uuid.RFC_4122
        assert value_uuid.version == 4

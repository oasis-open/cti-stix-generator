import json

import pytest
import stix2
import stix2.exceptions

import stix2generator
import stix2generator.generation.object_generator
import stix2generator.language.builder


def get_stix21_spec_names():
    """
    Gets the spec names from the STIX 2.1 registry.  We need to know this to
    be able to test those specifications.
    """
    registry = stix2generator._get_registry("2.1")

    return registry.keys()


STIX21_SPEC_NAMES = get_stix21_spec_names()


@pytest.fixture(scope="module")
def generator_random_props():
    """
    Creates a generator which randomly includes or excludes properties.
    """
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False
    )

    generator = stix2generator.create_object_generator(config, None, "2.1")

    return generator


@pytest.fixture(scope="module")
def generator_min_props():
    """
    Creates a generator which omits all optional properties.
    """
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False,
        optional_property_probability=0
    )

    generator = stix2generator.create_object_generator(config, None, "2.1")

    return generator


@pytest.fixture(scope="module")
def generator_all_props():
    """
    Creates a generator which includes all optional properties.
    """
    config = stix2generator.generation.object_generator.Config(
        minimize_ref_properties=False,
        optional_property_probability=1
    )

    generator = stix2generator.create_object_generator(config, None, "2.1")

    return generator


@pytest.mark.parametrize("spec_name", STIX21_SPEC_NAMES)
def test_generation_random_props(generator_random_props, spec_name, num_trials):

    for _ in range(num_trials):
        obj_dict = generator_random_props.generate(spec_name)

        # Ensure json-serializability
        json.dumps(obj_dict, ensure_ascii=False)

        # Distinguish between a STIX object spec and a "helper" spec used
        # by STIX object specs.  Only makes sense to stix2.parse() the former.
        if spec_name[0].isupper():
            try:
                stix2.parse(obj_dict, version="2.1")
            except stix2.exceptions.ParseError:
                # Maybe we can use this to mean this was an SCO?
                # Try a re-parse as an SCO.  Need a better way to make the
                # distinction...
                stix2.parse_observable(obj_dict, version="2.1")


@pytest.mark.parametrize("spec_name", STIX21_SPEC_NAMES)
def test_generation_min_props(generator_min_props, spec_name):

    obj_dict = generator_min_props.generate(spec_name)

    # Ensure json-serializability
    json.dumps(obj_dict, ensure_ascii=False)

    # Distinguish between a STIX object spec and a "helper" spec used
    # by STIX object specs.  Only makes sense to stix2.parse() the former.
    if spec_name[0].isupper():
        try:
            stix2.parse(obj_dict, version="2.1")
        except stix2.exceptions.ParseError:
            # Maybe we can use this to mean this was an SCO?
            # Try a re-parse as an SCO.  Need a better way to make the
            # distinction...
            stix2.parse_observable(obj_dict, version="2.1")


@pytest.mark.parametrize("spec_name", STIX21_SPEC_NAMES)
def test_generation_all_props(generator_all_props, spec_name):

    obj_dict = generator_all_props.generate(spec_name)

    # Ensure json-serializability
    json.dumps(obj_dict, ensure_ascii=False)

    # Distinguish between a STIX object spec and a "helper" spec used
    # by STIX object specs.  Only makes sense to stix2.parse() the former.
    if spec_name[0].isupper():
        try:
            stix2.parse(obj_dict, version="2.1")
        except stix2.exceptions.ParseError:
            # Maybe we can use this to mean this was an SCO?
            # Try a re-parse as an SCO.  Need a better way to make the
            # distinction...
            stix2.parse_observable(obj_dict, version="2.1")


# Test "relationship" separately since it is lower-cased, but nevertheless
# parseable by stix2.  I wanted to keep it all lower-case so people
# couldn't use it like an SDO/SCO in the prototyping language.

def test_generation_random_props_relationship(
    generator_random_props, num_trials
):
    for _ in range(num_trials):
        rel_dict = generator_random_props.generate("relationship")
        json.dumps(rel_dict, ensure_ascii=False)
        stix2.parse(rel_dict, version="2.1")


def test_generation_min_props_relationship(generator_min_props):
    rel_dict = generator_min_props.generate("relationship")
    json.dumps(rel_dict, ensure_ascii=False)
    stix2.parse(rel_dict, version="2.1")


def test_generation_all_props_relationship(generator_all_props):
    rel_dict = generator_all_props.generate("relationship")
    json.dumps(rel_dict, ensure_ascii=False)
    stix2.parse(rel_dict, version="2.1")


# Similar for sightings.

def test_generation_random_props_sighting(
    generator_random_props, num_trials
):
    for _ in range(num_trials):
        rel_dict = generator_random_props.generate("sighting")
        json.dumps(rel_dict, ensure_ascii=False)
        stix2.parse(rel_dict, version="2.1")


def test_generation_min_props_sighting(generator_min_props):
    rel_dict = generator_min_props.generate("sighting")
    json.dumps(rel_dict, ensure_ascii=False)
    stix2.parse(rel_dict, version="2.1")


def test_generation_all_props_sighting(generator_all_props):
    rel_dict = generator_all_props.generate("sighting")
    json.dumps(rel_dict, ensure_ascii=False)
    stix2.parse(rel_dict, version="2.1")

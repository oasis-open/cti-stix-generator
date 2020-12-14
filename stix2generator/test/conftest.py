import pytest

import stix2generator
import stix2generator.generation.object_generator


@pytest.fixture(scope="session")
def num_trials():
    """
    Since STIX content generation is random, depending on the test, we should
    do several trials so there is a greater chance for errors to occur.  This
    gives a global place to adjust how many trials are done for content
    generation tests.
    """
    # ... or should this just be a global var imported into test modules?
    return 10


@pytest.fixture(scope="session")
def object_generator():
    """
    Creates an object generator with default config and an empty registry.
    """
    return stix2generator.generation.object_generator.ObjectGenerator()


@pytest.fixture(scope="session")
def stix21_generator():
    """
    Creates a STIX generator with default config for STIX 2.1.
    """
    gen = stix2generator.create_stix_generator(stix_version="2.1")

    return gen

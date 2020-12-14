import json
import os.path

import faker

import stix2generator.language.builder
import stix2generator.generation.object_generator
import stix2generator.generation.reference_graph_generator
import stix2generator.generation.semantics
import stix2generator.generation.stix_generator
from stix2generator.exceptions import RegistryNotFoundError

try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

_STIX_REGISTRIES = {
    "2.1": "stix21_registry.json"
}


def _get_registry(stix_version):
    """
    Get the object generator registry for the given STIX version.

    :param stix_version: a STIX version
    :return: An object generator registry, as parsed JSON
    :raises stix2generator.exceptions.RegistryNotFoundError: If there isn't a
        built-in registry for the given STIX version
    :raises IOError: (python 2) If the registry JSON file couldn't be opened
        or read
    :raises OSError: (python 3) If the registry JSON file couldn't be opened
        or read (IOError is retained as an alias for backward compatibility).
    """
    if stix_version not in _STIX_REGISTRIES:
        raise RegistryNotFoundError(stix_version)

    spec_registry_path = os.path.join(
        os.path.dirname(__file__),
        _STIX_REGISTRIES[stix_version]
    )

    with open(spec_registry_path, encoding="utf-8") as f:
        spec_registry = json.load(f)

    return spec_registry


def create_object_generator(
    object_generator_config=None, extra_specs=None, stix_version="2.1"
):
    """
    Create an instance of the built-in object generator.

    :param object_generator_config: A Config object with generator settings,
        or None to use defaults.
    :param extra_specs: Any extra specifications which should be added to the
        built-in specs this generator will use, or None if there aren't any.
        The extra specs are overlaid on the built-in specs, so built-in specs
        can be overridden this way. (dict)
    :param stix_version: The STIX version to use, as a string ("2.0", "2.1",
        etc).
    :return: The object generator
    :raises stix2generator.exceptions.RegistryNotFoundError: If there isn't a
        built-in registry for the given STIX version
    :raises IOError: (python 2) If the registry JSON file couldn't be opened
        or read
    :raises OSError: (python 3) If the registry JSON file couldn't be opened
        or read (IOError is retained as an alias for backward compatibility).
    """

    spec_registry = _get_registry(stix_version)

    if extra_specs:
        _update_dict_recursive(spec_registry, extra_specs)

    stix_semantics = stix2generator.generation.semantics.STIXSemantics()

    faker_ = faker.Faker()
    faker_semantics = stix2generator.generation.semantics.FakerSemantics(faker_)

    semantics_providers = [
        stix_semantics,
        faker_semantics
    ]

    generator = stix2generator.generation.object_generator.ObjectGenerator(
        spec_registry,
        semantics_providers,
        object_generator_config
    )

    return generator


def create_stix_generator(
    object_generator_config=None,
    ref_graph_generator_config=None,
    stix_generator_config=None,
    extra_specs=None,
    stix_version="2.1"
):
    object_generator = create_object_generator(
        object_generator_config, extra_specs, stix_version
    )

    ref_graph_generator = stix2generator.generation.reference_graph_generator \
        .ReferenceGraphGenerator(
            object_generator, ref_graph_generator_config, stix_version
        )

    stix_generator = stix2generator.generation.stix_generator.STIXGenerator(
        object_generator, ref_graph_generator, stix_generator_config,
        stix_version
    )

    return stix_generator


def _update_dict_recursive(base_dict, new_dict):
    """
    Recursively updates a dictionary.

    :param base_dict: The original dictionary that will be updated in place.
    :param new_dict: The dictionary of values to update the original one with.
    :return: The updated dictionary
    """

    for key, val in new_dict.items():
        if isinstance(val, Mapping):
            base_dict[key] = _update_dict_recursive(base_dict.get(key, {}), val)
        else:
            base_dict[key] = val
    return base_dict


def create_default_language_processor(
    object_generator_config=None,
    extra_specs=None,
    stix_version="2.1"
):
    """
    Creates a language processor instance which uses the built-in object
    generator with the given settings.

    :param object_generator_config: Configuration information for the
        object generator, which will be used to generate any objects
        required by prototyping language this processor processes.
    :param extra_specs: Any extra specifications which should be added to
        the built-in specs this generator will use, or None if there aren't
        any.  The extra specs are overlaid on the built-in specs, so
        built-in specs can be overridden this way. (dict)
    :param stix_version: Which version of STIX to use.
    :return: A language processor instance
    """
    object_generator = create_object_generator(
        object_generator_config,
        extra_specs,
        stix_version
    )

    processor = stix2generator.language.builder.LanguageProcessor(
        object_generator, stix_version
    )

    return processor

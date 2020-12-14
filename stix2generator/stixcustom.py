import stix2
import stix2.base
import stix2.custom
import stix2.properties
import stix2generator
import stix2generator.exceptions
import stix2generator.generation.object_generator


_JSON_SIMPLE_TYPE_STIX_PROPERTY_MAP = {
    "string": stix2.properties.StringProperty,
    "number": stix2.properties.FloatProperty,
    "integer": stix2.properties.IntegerProperty,
    "boolean": stix2.properties.BooleanProperty
}


def _is_list_content_homogenous_type(list_):
    assert list_  # assume the list is not empty

    first_type = stix2generator.generation.object_generator._get_spec_type(
        list_[0]
    )

    result = all(
        stix2generator.generation.object_generator._get_spec_type(elt) == first_type
        for elt in list_[1:]
    )

    return result


def _prop_for_spec(prop_spec, stix_version):
    """
    Given an object generator spec, which is treated as a spec for a property
    value of an object, determine the type of value the spec generates and
    create a stix2 property instance which will accept values of that type.

    :param prop_spec: The object generator spec for a property value
    :param stix_version: The STIX version to use: "2.0", "2.1", etc.
    :return: A stix2 property object
    """
    prop_spec_type = stix2generator.generation.object_generator._get_spec_type(
        prop_spec
    )

    if prop_spec_type in _JSON_SIMPLE_TYPE_STIX_PROPERTY_MAP:
        prop_class = _JSON_SIMPLE_TYPE_STIX_PROPERTY_MAP[prop_spec_type]
        prop_obj = prop_class()

    elif prop_spec_type == "object":
        # DictionaryProperty needs a spec_version parameter.
        prop_obj = stix2.properties.DictionaryProperty(
            spec_version=stix_version
        )

    elif prop_spec_type == "array":
        # For arrays, we need to know the element type.
        if isinstance(prop_spec, list):
            # const array spec.  The list must be non-empty and of homogenous
            # type for us to be able to infer a stix2 property.
            if not prop_spec:
                raise stix2generator.exceptions.EmptyListError()
            if not _is_list_content_homogenous_type(prop_spec):
                raise stix2generator.exceptions.HeterogenousListError(prop_spec)

            element_spec = prop_spec[0]

        else:
            element_spec = prop_spec["items"]

        element_prop_obj = _prop_for_spec(element_spec, stix_version)
        prop_obj = stix2.properties.ListProperty(element_prop_obj)

    else:
        # Maybe we just hit this for "null" specs?
        raise stix2generator.exceptions.IllegalSTIXObjectPropertyType(
            prop_spec_type
        )

    return prop_obj


def stix2_register_custom(spec, obj_type_name, stix_version):
    """
    Dynamically derive a simple Python class for the given object generator
    spec, and register it as a custom SDO with the stix2 library under the
    given name.

    :param spec: An object generator spec for a STIX object, as a dict
    :param obj_type_name: The desired STIX type name to register it as
    :param stix_version: The STIX version to use: "2.0", "2.1", etc.
    """
    spec_type = stix2generator.generation.object_generator._get_spec_type(spec)

    if spec_type != "object":
        raise stix2generator.exceptions.IllegalSTIXObjectSpecType(spec_type)

    if "const" in spec:
        # A const object spec must be a dict with "const" key whose value is
        # a dict.  We will treat every property value in that dict as a const
        # spec.
        const_object = spec["const"]
        prop_specs = {
            prop_name: {"const": prop_value}
            if isinstance(prop_value, dict) else prop_value
            for prop_name, prop_value in const_object.items()
        }
    else:
        prop_specs = spec.get("properties", {})

    prop_map = [
        (prop_name, _prop_for_spec(prop_spec, stix_version))
        for prop_name, prop_spec in prop_specs.items()
    ]

    custom_class = type(
        "AutoRegisteredType_" + obj_type_name,
        (object,), {}
    )

    if stix_version == "2.1":
        stix_decorator = stix2.v21.CustomObject
    else:
        stix_decorator = stix2.v20.CustomObject

    stix_decorator(obj_type_name, prop_map)(custom_class)


def stix2_auto_register_all_custom(specs, stix_version):
    """
    Detect which of the given object generator specs are for "custom" objects,
    try to dynamically derive simple Python classes, and register them with the
    stix2 library as custom SDOs so that using those custom types with the
    prototyping language is possible.

    Custom STIX object specs are detected as:
      - Spec name starts with a capital letter
      - Spec name is not in the builtin object generator spec registry for the
        given STIX version

    :param specs: A mapping from name -> object generator spec
    :param stix_version: The STIX version to use: "2.0", "2.1", etc.
    """
    builtin_registry = stix2generator._get_registry(stix_version)

    custom_object_spec_names = (
        spec_name for spec_name in specs
        if spec_name and spec_name[0].isupper() and
        spec_name not in builtin_registry
    )

    for custom_object_spec_name in custom_object_spec_names:
        custom_object_spec = specs[custom_object_spec_name]
        custom_object_props = custom_object_spec.get('properties', {})
        try:
            stix2_register_custom(
                custom_object_spec,
                custom_object_props.get(
                    'type', custom_object_spec_name.lower()
                ),
                stix_version
            )
        except stix2generator.exceptions.AutoRegistrationError as e:
            if not e.spec_name:
                e.spec_name = custom_object_spec_name

            raise

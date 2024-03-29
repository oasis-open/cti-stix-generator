Object Generator
================

This document describes the built-in object generator.  An object generator is
responsible for generating all of the STIX domain/cyber-observable objects when
STIX prototyping language is converted to STIX.

Design Principles
-----------------

A basic design principle is that the object generator is really a JSON
generator, with features added as necessary so that it can build JSON
serializations of compliant STIX objects.

It was also designed to be configurable by non-programmers.  The layout and
constraints of STIX objects is not hard-coded into the generator.  Generation
is governed by a "specification", which is JSON data.  You can change and add
to what is generated by editing a JSON file, which makes it possible to modify
many aspects of generation without programming.  Since it's regular data, it's
also modifiable at run-time if a tool wanted to have that capability, e.g. to
add custom STIX objects.

JSON-Schema was one source of inspiration for the design of specifications.
Some terminology and structure was borrowed, so some aspects of specifications
should look familiar to those who have used that technology.

Object generator instances operate from a database of sorts which contains
specifications organized by name.  This database is called a *registry*.  Apart
from being a convenient way of organizing things, it also enables name-based
references within specifications.

Correctness and Completeness
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It should be stated up front that the generator specification language and
object generator are not able to generate every variant of compliant STIX
object.  Some STIX requirements are rather complex, the STIX specification is a
moving target as it evolves, and it is perhaps unrealistic to expect that
the generator specifications can or should exactly represent the STIX
specification.  The STIX prototyping language tool is intended to be a way for
people to experiment with different graph structures; the quality of generated
STIX objects is of secondary importance.

The limitations of the object generator may be thought of in terms of
*correctness* and *completeness*.  In this context, "correctness" means that
all generated STIX content is compliant with the STIX specification.
Completeness means that all compliant STIX may be generated.  The goal of the
object generator is that it be correct, but it need not be complete.

Specifications
--------------

The object generator generates JSON values which are of a fixed set of types.
These include all the JSON types, plus ``integer``, which was borrowed from
JSON-Schema and seemed useful to include.  More specifically, being a Python
library, it generates JSON-serializable values.  The mapping between JSON and
Python types is as follows:

+--------+------------+
|  JSON  |   Python   |
+========+============+
| string | str        |
+--------+------------+
| number | float      |
+--------+------------+
| integer| int        |
+--------+------------+
| null   | None       |
+--------+------------+
| boolean| bool       |
+--------+------------+
| array  | list       |
+--------+------------+
| object | dict       |
+--------+------------+

The reverse mapping also holds, where ``int`` always maps to the generator's
integer type.

Constant Specifications
~~~~~~~~~~~~~~~~~~~~~~~

Every value of the above types is a specification.  If the value is not
an object, then the specification simply generates that value.  It's a simple
way to generate fixed values.  Another way to generate fixed values is to use
an object with a "const" property:

.. code:: json

    {
        "const": 123
    }

This form is necessary for generating fixed JSON objects.

Non-constant Specifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~

These specifications are all objects.  They all share one common property,
``type``.  This helps readers easily determine at a glance what type of value any
specification will generate.  The value of the ``type`` property must be one of
the JSON types from the table above.

The choice of ``type`` determines what other properties are necessary for
expressing what to generate.  The supported properties for the various JSON
types are given below.

String Specifications
^^^^^^^^^^^^^^^^^^^^^

+-----------+---------------------------+
| Property  |      Description          |
+===========+===========================+
| minLength | The minimum string length |
+-----------+---------------------------+
| maxLength | The maximum string length |
+-----------+---------------------------+

A string of a random length with a random mix of characters is generated.

Number Specifications
^^^^^^^^^^^^^^^^^^^^^

+------------------+-------------------------------+
|     Property     |          Description          |
+==================+===============================+
| minimum          | The minimum value (inclusive) |
+------------------+-------------------------------+
| maximum          | The maximum value (inclusive) |
+------------------+-------------------------------+
| exclusiveMinimum | The minimum value (exclusive) |
+------------------+-------------------------------+
| exclusiveMaximum | The maximum value (exclusive) |
+------------------+-------------------------------+

A random floating point number is generated within the given bounds.

Integer Specifications
^^^^^^^^^^^^^^^^^^^^^^

+------------------+-------------------------------+
|     Property     |          Description          |
+==================+===============================+
| minimum          | The minimum value (inclusive) |
+------------------+-------------------------------+
| maximum          | The maximum value (inclusive) |
+------------------+-------------------------------+
| exclusiveMinimum | The minimum value (exclusive) |
+------------------+-------------------------------+
| exclusiveMaximum | The maximum value (exclusive) |
+------------------+-------------------------------+

A random integer is generated within the given bounds.  The bounds need not be
integers.

Null Specifications
^^^^^^^^^^^^^^^^^^^

No properties are supported.  This specification type always generates None.

Boolean Specifications
^^^^^^^^^^^^^^^^^^^^^^

No properties are supported.  This specification type will randomly generate
True or False with equal probability.

Array Specifications
^^^^^^^^^^^^^^^^^^^^

+----------+-------------------------------------------+
| Property |                Description                |
+==========+===========================================+
| minItems | The minimum array length                  |
+----------+-------------------------------------------+
| maxItems | The maximum array length                  |
+----------+-------------------------------------------+
| items    | A specification use to generate all items |
+----------+-------------------------------------------+

A list of random length is generated, where each element is generated via the
``items`` specification.

Object Specifications
^^^^^^^^^^^^^^^^^^^^^

+------------------------+-----------------------------------------------------------+
|       Property         |                        Description                        |
+========================+===========================================================+
| properties             | A dict containing property names and their specifications |
+------------------------+-----------------------------------------------------------+
| import                 | The name of another object specification                  |
+------------------------+-----------------------------------------------------------+
| required               | A list of required property names/groups                  |
+------------------------+-----------------------------------------------------------+
| optional               | A list of optional property names/groups                  |
+------------------------+-----------------------------------------------------------+
| value-coconstraints    | Value co-constraints                                      |
+------------------------+-----------------------------------------------------------+
| presence-coconstraints | Presence co-constraints                                   |
+------------------------+-----------------------------------------------------------+

A dict is generated according to the given constraints and specifications.
This specification type is the most complicated.  All STIX objects map to this
type, and so all of the complexity of expressing their constraints is here.

``import`` is a way of factoring out commonalities among several object
specifications.  STIX objects share many properties, e.g. those for ID and
versioning, so it is advantageous to be able to define those in one place.
The imported specification must be of type object.

``properties`` is a dict where each key names a property which may be present on
the generated dict, and the value is a specification used to generate the value.

``required`` and ``optional`` express which properties and/or property groups are
required and optional in generated dicts.  Both cannot be present.  If neither
is present, all properties/groups are treated as required.

``value-coconstraints`` and ``presence-coconstraints`` are for expressing
co-constraints on property values, and are described in the
`co-constraints <#co-constraints>`__ section.

The overall procedure for generating an object is as follows:

1. The imported object is constructed; it will be used as a "base" to which
   all properties from this specification will be added.
2. Properties are chosen according to optionality and presence co-constraints.
3. Values are generated for the properties selected in step 2.

Steps 2 and 3 are independent of the imported object: constraints in the
importing specification must not reference properties in the imported object.

Co-constraints
~~~~~~~~~~~~~~

In this context, a *co-constraint* is a restriction on a property which is not
relative to something fixed, it is relative to another property.  It implies
restrictions on both properties simultaneously.  For example, that the value of
one property be less than another.

In studying the STIX specification and trying to tease out some common themes,
co-constraints of two basic types were found, which we refer to as *value* and
*presence*.  A value co-constraint restricts properties' values.  A presence
co-constraint restricts how properties may coexist with each other.

Co-constraints, if not handled carefully, can result in a lot of complexity.
For example, they can be impossible to satisfy, or there can be ripple effects
where satisfying one can have implications for how one can satisfy others.  In
order to keep the implementation and specifications simple, there are
restrictions on what you're allowed to do.

Value Co-constraints
^^^^^^^^^^^^^^^^^^^^

The `value-coconstraints` property of an object specification takes the form
of a list of strings, where each string expresses the constraint using a
simple syntax.  The syntax consists of two property names with an operator
between them.  The valid operators are ``=``, ``!=``, ``<``, ``<=``, ``>``,
``>=``.

Enforcement of value co-constraints is severely restricted.  It was only found
to be necessary for timestamp-valued properties of certain objects, so they
are currently only propagated to `semantics <#semantics>`__ implementations, and
only the ``stix-timestamp`` semantics currently honors them.

For example:

.. code:: json

    {
        "value-coconstraints": ["first_seen <= last_seen"]
    }

Presence Co-constraints
^^^^^^^^^^^^^^^^^^^^^^^

Presence co-constraints are expressed in various ways in the STIX specification.
For example, "if property A is present, then property B must also be present".
Or "at least one of properties A, B, C must be present".  These statements are
all about the conditions under which a property is allowed to (or must) be
present in an object.  Presence co-constraints are intended to express these
kinds of restrictions in object specifications.

Presence co-constraints can be broken down into two broad categories: those
which identify a group of properties and impose conditions identically across
all members of the group, and those which don't.  An example of the first type
of presence co-constraint is "at least one of properties A, B, C must be
present".  That statement doesn't call out any member of the group specially;
they are all treated the same.  An example of the latter is "if property A is
present, then property B must also be present".  This type of presence
co-constraint essentially endows property A with a special control over B.  If
A is present, we have the requirement that B must be present.  If A is not
present, then the co-constraint doesn't apply, and imposes no conditions.  This
type of co-constraint is therefore asymmetric: B doesn't have the same
influence over A.

The ``presence-coconstraints`` property in an object specification is
object-valued, and encompasses both types of presence co-constraints.  An
example structure which includes samples of all its parts is:

.. code:: json

    {
        "property-groups": {
            "group-a": ["prop1", "prop2"],
            "group-b": ["prop3", "prop4"],
            "group-c": ["prop5", "prop6"]
        },
        "one": ["group-a"],
        "all": ["group-b"],
        "at-least-one": ["group-c"],
        "dependencies": {
            "prop5": ["prop7", "prop8"]
        }
    }

The ``dependencies`` property is used for expressing asymmetric presence
co-constraints and was named after a similar JSON-Schema property.  The rest
are for symmetric co-constraints.

The rules one must follow when defining these presence co-constraints are:

- Property groups must be disjoint
- Grouped properties must not be individually referenced
- Property groups must not be empty
- Property groups should have more than one member.  Length one property groups
  have some sanity checking done, but are otherwise ignored.
- Property group names must not conflict with property names
- Every property group must be assigned exactly one constraint type

Symmetric Presence Co-constraints
*********************************

The essential construct of a symmetric presence co-constraint is the property
group.  One then assigns a constraint type to the group, of which three are
supported: ``one``, ``all``, and ``at-least-one``.  In addition, the
``required`` and ``optional`` properties of object specifications are enhanced to
support listing these groups, in addition to ordinary properties.

Putting the co-constraint type and optionality together, one can obtain a
variety of presence co-constraint behaviors:

+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| required | constraint type |                    description                                                                                                                                        |
+==========+=================+=======================================================================================================================================================================+
| yes      | one             | Exactly one property of the group must be present.                                                                                                                    |
+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| no       | one             | All properties are optional, but if one is present, no others may be present.                                                                                         |
+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| yes      | all             | All properties are required.  This is the same as making all properties individually required. It is preferable to do that instead of using a presence co-constraint. |
+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| no       | all             | All properties are optional, but if one is present, all others must also be present.                                                                                  |
+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| yes      | at-least-one    | At least one property from the group must be present.                                                                                                                 |
+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| no       | at-least-one    | All properties are optional.  This is the same as making all properties individually optional.  It is preferable to do that instead of using a presence co-constraint.|
+----------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+

Asymmetric Presence Co-constraints
**********************************

The value of the ``dependencies`` property is a JSON object.  Each key in the
object may name either a property or a group, and the corresponding value is a
list of the same.  The meaning is that if the key (property or group) is present
in the generated object, then all of the given values must also be present.
Other permutations of the idea (e.g. "if A is not present, then B must be
present") are not currently expressible, and have not so far been necessary.

Similar rules apply here as for symmetric presence co-constraints.
Additionally, keys and values must be disjoint sets.  This avoids dependency
ripple effects where presence of one property/group implies that presence of
another is required, which implies presence of another is required, etc.

Miscellaneous Specification Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are some miscellaneous keys one can use in an object specification, to
get additional behaviors: ``ref`` and ``oneOf``.

Specification References: ``ref``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``ref`` property allows a specification to refer to another one.  The name
is looked up in the object generator's registry.  This can be helpful when one
wants to reuse a specification in multiple contexts without being repetitive.
The type of the referring specification must match with the referred-to
specification, or an error will result.

For example:

.. code:: json

    {
        "type": "string",
        "ref": "some-vocab"
    }

Specification Alternation: ``oneOf``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``oneOf`` property is a way of causing generation to be done via a randomly
chosen sub-specification.  Each sub-specification must be of the same type as
the parent.

For example:

.. code:: json

    {
        "type": "string",
        "oneOf": [
            "term1",
            "term2"
        ]
    }

This example illustrates how one might write a specification which picks a
random word from a vocabulary.

An alternative structure is also available which allows weighting the
alternatives differently.  The structure is an object with ``choices`` and
``weights`` keys.  For example:

.. code:: json

    {
        "type": "string",
        "oneOf": {
            "choices": ["term1", "term2"],
            "weights": [1, 2]
        }
    }

The weights are normalized to a probability distribution.  In this example,
"term2" will be chosen twice as often as "term1".  The general rules for this
structure include:

- ``choices`` must be a list of specifications
- ``weights`` must be a list of numbers (need not be integers)
- The choices and weights lists must be the same length
- The choices and weights lists must not be empty
- No weight may be negative
- At least one weight must be positive

Semantics
---------

Some values have detailed formatting or other requirements for which it was
decided that expressing their rules in detail in a specification was
unsuitable.  The *semantics* mechanism can be seen as a sort of "escape hatch"
for things a specification can't or shouldn't express.  It is a way to trigger
generation via some custom Python code.  Ideally, one should need to rely on
semantics only for small reusable things like STIX IDs and timestamps.  The
word "semantics" reflects its role in specifications and how they read, as
augmenting the basic ``type`` property by expressing a deeper meaning, as opposed
to replacing the property.

Usage of the semantics mechanism is signaled via a special property:
``semantics``.  The property value is looked up internally to find the
implementation.  To allow behavioral customization by specification authors,
all other properties are made available to the semantics implementation for use
in any way it wishes.

For example, generating STIX IDs is done via this mechanism:

.. code:: json

    {
        "type": "string",
        "semantics": "stix-id",
        "stix-type": "identity"
    }

Here, the type is ``string``, but more specifically is a random ID of an
``identity`` STIX object.

Currently Supported Semantics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The semantics supported by the built-in object generator by default include:

stix-id
^^^^^^^

This semantics is used to generate STIX IDs.  It takes one property,
``stix-type``, which gives the type of STIX object the ID should be generated
for.  An example of this was given above.

stix-timestamp
^^^^^^^^^^^^^^

This semantics is used to generate STIX formatted timestamps as strings.  It
does not require any other properties.  It is currently written to generate a
timestamp within a year (future or past) of the current date and time, or the
constraining date and time if such a constraint is in effect.

This is currently the only type of generation which honors
`value co-constraints <#value-co-constraints>`__.

For example:

.. code:: json

    {
        "type": "string",
        "semantics": "stix-timestamp"
    }

Faker semantics
^^^^^^^^^^^^^^^

All faker functions from the `Faker <https://faker.readthedocs.io/>`__ library are
available as semantics.  The semantics name is the function name, and other
properties are passed through to the faker function as keyword arguments.

For example:

.. code:: json

    {
        "type": "array",
        "semantics": "words",
        "nb": 3
    }

This invokes the "words" faker function from that library's
`lorem <https://faker.readthedocs.io/en/master/providers/faker.providers.lorem.html>`__
provider, with ``nb=3`` which causes three words to be generated.

Implementation Notes
--------------------

With respect to the STIX prototyping language processor, the final fate of
generated STIX objects is to be parsed by the ``stix2`` library.  The latter
library can be flexible with respect to property values.  For example, if a
property is defined to have string type in that library, it will try to
convert non-strings to strings.  This implies some flexibility in object
generator specifications.  For example, a specification could generate an
integer value for a string property, and stix2 would automatically convert that
to a string.  This is a clever way to generate ints-as-strings.  The built-in
specifications may sometimes take advantage of that flexibility and not be of
the type you expect.

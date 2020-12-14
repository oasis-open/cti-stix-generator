STIX Prototyping Language
=========================

The STIX prototyping language is intended to be a simple, readable way to
express STIX object graphs.  This library can automatically create STIX content
from the language.  The language and library can be useful for creating content
for testing and experimentation.

Basic Syntax
------------

The language is composed of a sequence of statements.  Each statement is
terminated by a period, like an English sentence.  STIX domain objects and
relationships are referenced by name.  Domain objects must begin with a capital
letter and contain only letters and underscores; relationships must begin with
lower case.  In following with the STIX specification, relationship names may
contain only lowercase alphanumerics and hyphens.  They must begin with a
letter.

The simplest statement names a single SDO:

.. code::

    Identity.

To relate two objects together:

.. code::

    Malware targets Identity.

When SDOs are named this way, they have no reusable identity within the
language.  That means each use indicates a different object:

.. code::

    Attack_Pattern uses Malware.
    Malware targets Identity.

Here, the two ``Malware`` objects are different.  Object reuse may be accomplished
with other syntax.

Multiplicity
------------

Lists of objects are expressed with parentheses:

.. code::

    (Identity Location).

This silly example means the same as if the two objects were in separate
statements.  But lists can be used as sources and targets of relationships:

.. code::

    Attack_Pattern uses (Malware Tool).

This relates an attack pattern to both a ``malware`` and a ``tool`` object, via
different relationships.  It has a different meaning than if two statements
were used: both relationships share the *same* source.  If two statements had
been used, the relationships would have two different sources.  It is an
analogous situation if the list had been in the source position.

If a list is in both the source and target position, then all objects in the
source are related to all objects in the target.  This is similar to a set-
theoretic Cartesian product, or a relational join.  If there are N objects in
the source and M objects in the target, N*M relationships are created.

Counts
~~~~~~

An integer count prefix can be given, which means the same as a homogenous list:

.. code::

    2 Identity.

This means the same as ``(Identity Identity)``.  A count prefix may occur most
places an object type name is allowed.  This makes it usable in contexts where a
list is not allowed, e.g. inside another list:

.. code::

    (Malware 2 Identity).

This means one ``malware`` object and two ``identity`` objects.

Lastly, counts are allowed on relationships, which has the effect of creating
multiple parallel edges in the graph:

.. code::

    Attack_Pattern 2 uses (Malware Tool).

This relates a single ``attack-pattern`` to a ``malware`` and a ``tool``, but two
relationships each are created, for a total of four relationships.

Chaining
--------

A relationship between a source and target can be chained to another target:

.. code::

    Attack_Pattern delivers Malware targets Identity.

This represents two relationships, where the ``malware`` delivered by the
``attack-pattern`` is the same one which targets the ``identity``.  This is another
way of reusing an object.  These chains can be arbitrarily long.

Property Blocks
---------------

Property blocks are primarily used to represent embedded relationships, i.e.
those which are realized in STIX via an object property, not an SRO.  They use
a JSON object-like syntax with curly braces, positioned after the object
type name:

.. code::

    Report {
        object_refs: (Malware)
    }.

Note that a length-1 list is used because the STIX property is list-valued.

The property name must not be quoted, and the property value may be any STIX
prototyping language graph statement, including relationships and nested
property blocks.  When a more complex graph is used as a property value, it is
the top-level source objects which are assigned to the property.  In keeping
with STIX spec requirements on property names, these names may consist of
lowercase alphanumerics and underscores only.  They must begin with a letter.

String Literals
~~~~~~~~~~~~~~~

String literals are the only primitive literal type supported in the prototyping
language, and are only supported in property blocks.  The primary purpose of
string literals is to assign simple names to things, to assist people in
matching up generated STIX objects to components of language statements.  When
usage is more complex and/or generates numerous objects, it can otherwise be
difficult to understand what was generated.  Graphical visualization tools
sometimes use certain properties to create graph labels.  For example, some
objects have a "name" property, and "labels" is a common property.  

String literals are enclosed in double quotes.  Lists of literals can be
expressed with square brackets:

.. code::

    Malware {name: "Downloader"} downloads Malware {name: "Backdoor"}.

and

.. code::

    Indicator {
        labels: ["label1", "label2"]
    }.

Special Relationship Syntax
---------------------------

In order to make STIX prototyping language more English-like, some relationship
names are treated specially: ``on`` and ``of``.  These special relationships may not
have counts.

object_refs and `on`
~~~~~~~~~~~~~~~~~~~~

``on`` is a shorthand used to set the ``object_refs`` property of an object, and
may be used instead of a property block.  The statement looks like others which
represent SRO relationships, but it doesn't do that.  If you use this special
syntax on a source object, you can't also relate it to a target via a normal
SRO relationship.  You may still use a property block on the source object to
populate other properties.  For example:

.. code::

    Report on (Malware Campaign).

Sightings and `of`
~~~~~~~~~~~~~~~~~~

Sightings are a special relationship type which breaks the mold of all other
SROs.  They are ternary (relate up to three things), and don't have the usual
SRO property names.  So they don't fit with the normal infix notation of other
relationships.  A sighting statement begins with ``Sighting`` and may be followed
by ``of`` to represent the required ``sighting_of_ref`` property:

.. code::

    Sighting of Malware.

The other related objects must be represented in a property block:

.. code::

    Sighting {
        observed_data_refs: (Observed_Data),
        where_sighted_refs: 2 Location
    } of Malware.

If desired, ``sighting_of_ref`` can also be given in a property block, and the
trailing ``of`` clause omitted:

.. code::

    Sighting {
        observed_data_refs: (Observed_Data),
        where_sighted_refs: 2 Location,
        sighting_of_ref: Malware
    }.

Note that ``Sighting`` *must not* have a count prefix, or it will be interpreted
as a "normal" graph statement, not this special syntax.

Variables
---------

If other methods of object reuse won't work or are undesirable, the language
supports variables.  A variable declaration statement looks like:

.. code::

    var_a, var_b: Identity.

Variable names must be all lowercase, begin with a letter, and consist of
alphanumerics, hyphens, and underscores only.  Variables may only hold domain
objects; they may not hold relationships.

Where *used*, a variable may not have either a count or a property block.  Where
*declared*, it may have both:

.. code::

    malware_a {name: "bad malware"}: Malware.
    2 victims {name: "a victim"}: Identity.

    malware_a targets victims.

The count on a variable is given before the variable name, similar to how it is
done with domain objects and relationships in normal graph statements.  This
allows variables to hold multiple values.  The above represents a ``malware``
targeting two ``identity`` objects, the "victims".

Property blocks on variables may use other variables.  This creates dependencies
among them.  Declaration order is unimportant; the tool figures out an
appropriate initialization order automatically:

.. code::

    note {object_refs: (loc id)}: Note.
    loc: Location.
    id: Identity.

    Report on note.

A dependency cycle will cause an error.

Implementation Notes
--------------------

An obvious question to ask is what STIX object types are currently supported by
the library and what names do you use for them in the language.  The answer may
be counterintuitive, and requires some understanding of the library
architecture.

The library is composed of two components:
1. A language "processor"
2. An object generator

The first component is what understands the language and connects the objects
together.  The second component is a delegate of the first, and is responsible
for generating its objects.

So the counterintuitive answer to the question is that the language processor
has *no* hard-coded lists of STIX object names or properties.  Anything goes;
you just need to follow the lexical rules as described above.  E.g. that domain
objects start with capital letters and consist of letters and underscores,
everything else starts with lower case, etc.  STIX domain object names are
passed to the object generator, and if the latter component doesn't know how to
generate an object of that type, it will produce an error.  But that issue is
unrelated to the language itself.  You can also use any lexically legal
relationship name you want; the language processor will happily create an SRO
with that relationship type.  It knows little of the STIX specification.

Another important architectural point is that all objects generated by the
object generator, and by the language processor internally, are plain "parsed
JSON", i.e. simple Python values like dicts and lists.  It is not until the
very last step that those values are passed to the ``stix2`` library, from which
it creates the final objects which are returned.  So the latter library is a
dependency of this one.  It has its own STIX support, and does certain
compliance checks which none of the components of this library necessarily do.

The built-in object generator operates based on "specifications" contained in a
JSON data file; it doesn't have any STIX rules built into the programming.  The
advantage of all of this is that custom objects can potentially be supported
without reprogramming anything in this library at all!  (The stix2 library is a
different story though.)

So the final answer as to current STIX object support boils down to what object
types the object generator and the ``stix2`` library recognize.  The latter
library has its own documentation.  The built-in object generator in this
library recognizes the following types:

.. code::

    Attack_Pattern
    Campaign
    Course_of_Action
    Grouping
    Identity
    Indicator
    Infrastructure
    Intrusion_Set
    Location
    Malware
    Malware_Analysis
    Note
    Observed_Data
    Opinion
    Report
    Threat_Actor
    Tool
    Vulnerability
    Artifact
    Autonomous_System
    Directory
    Domain_Name
    Email_Address
    Email_Message
    File
    IPv4_Address
    IPv6_Address
    MAC_Address
    Mutex
    Network_Traffic
    Process
    Software
    URL
    User_Account
    Windows_Registry_Key
    X509_Certificate


import lark
import logging
import pprint
import stix2

from stix2generator.exceptions import (
    CircularVariableDependenciesError, LanguageError, RedeclaredVariableError,
    UndeclaredVariableError
)
from stix2generator.utils import (
    is_token, is_tree
)
import stix2generator.generation.semantics
import stix2generator.generation.object_generator
import stix2generator.logging


_grammar = r"""

// can we use the Lark-included string literal token?
%import common.ESCAPED_STRING

graph_spec : (statement ".")+

statement : variable_declaration_statement
  | graph_statement
  | sighting

variable_declaration_statement : variable_declaration ("," variable_declaration)* ":" SDO_TYPE_NAME

variable_declaration : count? VARIABLE_NAME property_block?

graph_statement : (sdo_ref | sdo_list) relationship?

relationship : count? RELATIONSHIP_NAME graph_statement

sdo_list : "(" sdo_ref+ ")"

sdo_ref : sdo_inline | VARIABLE_NAME

sdo_inline : count? SDO_TYPE_NAME property_block?

property_block : "{" [property_assignment ("," property_assignment)*] "}"

property_assignment : PROPERTY_NAME ":" (graph_statement | ESCAPED_STRING | string_array)

count : POSITIVE_INT

string_array : "[" [ESCAPED_STRING ("," ESCAPED_STRING)*] "]"

// This allows both the property block and "of" clause to be omitted
// (which will result in an error since "sighting_of_ref" is a required
// property), but it's simpler than expressing "at least one".
// Increase rule priority, since "Sighting of ..." is ambiguous w.r.t.
// graph_statement, with (supposed) sdo "Sighting" and relationship "of".
sighting.2 : "Sighting" property_block? ["of" graph_statement]

POSITIVE_INT : /[1-9][0-9]*/

SDO_TYPE_NAME : /[A-Z][A-Za-z0-9_]*/

// These definitions conflict; hopefully we can rely on Lark's
// terminal collision resolution.
RELATIONSHIP_NAME : /[a-z][a-z0-9-]*/
PROPERTY_NAME : /[a-z][a-z0-9_]*/
VARIABLE_NAME : /[a-z][a-z0-9_-]*/

WS : /[ \t\r\n\u000B\u000C\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000]+/

%ignore WS

"""


_parser = lark.Lark(
    _grammar,
    start="graph_spec",
    propagate_positions=True,
    # debug=True
)


# lazy-initialized
_log = None


# A custom property to use when embedding variable names in objects
_VARIABLE_NAME_PROPERTY = "x_viz_variable_name"


def _get_logger():
    global _log
    if _log is None:
        _log = logging.getLogger(__name__)

    return _log


def _make_object(object_generator, type_name, overlay_props=None):
    """
    Make an object via an object generator.

    :param object_generator: The generator to use
    :param type_name: The name of a spec, which the generator should recognize
    :param overlay_props: After having generated the object, a dict of
        property names and values which will be overlaid.  This can act to
        override generated property values.
    :return: The object, as a dict
    """

    sdo_dict = object_generator.generate(type_name)

    if overlay_props:
        sdo_dict.update(overlay_props)

    return sdo_dict


def _make_sro(object_generator, source_id, rel_type, target_id):
    """
    Make an SRO.

    :param source_id: The ID of the source object (string)
    :param rel_type: The relationship type (string)
    :param target_id: The ID of the target object (string)
    :return: The SRO, as a dict
    """

    rel = object_generator.generate("relationship")
    rel["source_ref"] = source_id
    rel["target_ref"] = target_id
    rel["relationship_type"] = rel_type

    return rel


def _make_sighting(object_generator, sighting_of, overlay_props=None):
    """
    Make a Sighting.

    :param sighting_of: A value for the sighting_of_ref property, or None to
        omit that property.
    :param overlay_props: After having generated the object, a dict of
        property names and values which will be overlaid.  This can act to
        override generated property values.
    :return: The sighting, as a dict
    """

    rel = object_generator.generate("sighting")

    if sighting_of:
        rel["sighting_of_ref"] = sighting_of
    if overlay_props:
        rel.update(overlay_props)

    return rel


def _print_parse_tree(logger, tree, indent=0):
    """
    A parse tree printer that's better than Lark's (in my opinion).  It shows
    token types as well as values (Lark's doesn't show the types).  It's done
    via the logger, at a custom extra-verbosity level.

    :param logger: The logger to use
    :param tree: The parse tree
    :param indent: An indent amount
    """
    line = " " * indent
    if is_token(tree):
        line += tree + " (" + tree.type + ")"
        logger.log(stix2generator.logging.EXTRA_VERBOSE, line)
    else:
        line += tree.data
        logger.log(stix2generator.logging.EXTRA_VERBOSE, line)
        for child in tree.children:
            _print_parse_tree(logger, child, indent + 1)


def _string_token_value(tok):
    """
    Given an ESCAPED_STRING token, unquote and unescape its value, to
    obtain the actual string it represents.

    :param tok: an ESCAPED_STRING token
    :return: The string value
    """
    return tok.value[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _topo_sort_dfs(dependencies, start_var, visited_vars, sorted_vars,
                   search_path):
    """
    Helper for topo sort, which does a post-order DFS from the given start
    variable to find the ordering.

    :param dependencies: The dependency data
    :param start_var: The start variable for the search
    :param visited_vars: Keeps track of which variables we've already seen,
        to prevent duplicates
    :param sorted_vars: A list which builds up the sort order
    :param search_path: A stack which records our DFS search path, so that
        we can detect cycles
    """

    visited_vars.add(start_var)
    search_path.append(start_var)

    if start_var in dependencies:
        for dep_var in dependencies[start_var]:

            if dep_var in search_path:
                cyclic_path = search_path[search_path.index(dep_var):]
                cyclic_path.append(dep_var)
                raise CircularVariableDependenciesError(cyclic_path)

            if dep_var not in visited_vars:
                _topo_sort_dfs(
                    dependencies, dep_var, visited_vars, sorted_vars,
                    search_path
                )

                sorted_vars.append(dep_var)

    search_path.pop()


def _topo_sort_dependencies(dependencies):
    """
    Topologically sorts the variables given in dependencies, to obtain a
    value creation order that is compatible with everyone's dependencies.

    :param dependencies: The dependency data, as a mapping from var name to
        a set of dependencies.  (This is basically an adjacency list
        representation of a directed graph.)
    :return: A list of variable names in sorted order
    :raises CircularVariableDependenciesError: If circular dependencies are
        encountered
    """
    visited_vars = set()
    sorted_vars = []

    for var_name in dependencies:
        if var_name not in visited_vars:
            _topo_sort_dfs(
                dependencies, var_name, visited_vars, sorted_vars, []
            )
            sorted_vars.append(var_name)

    return sorted_vars


def _remove_variable_declaration_statements(parse_tree):
    """
    Modify the parse tree by removing all variable declaration statements.
    This is an in-place modification: the given tree's list of children is
    modified.

    :param parse_tree: The whole parse tree (a subtree won't work)
    """

    indices_to_remove = [
        i for i, statement in enumerate(parse_tree.children)
        if statement.children[0].data == "variable_declaration_statement"
    ]

    # Easier to do in reverse order, so that deletions don't affect
    # subsequent indices.
    for i in reversed(indices_to_remove):
        del parse_tree.children[i]


class _VariableSpec:
    """
    Instances of this class serve as placeholders for variables which have
    dependencies.  They contain the information necessary to create a variable
    value later.  Their values aren't created when their declarations are
    encountered in the parse tree.
    """
    def __init__(self, var_name, var_count, var_type, var_props_tree):
        self.var_name = var_name
        self.var_count = var_count
        self.var_type = var_type
        self.var_props_tree = var_props_tree

    def __str__(self):
        s = "Placeholder for '{}', count={}, type={}".format(
            self.var_name, self.var_count, self.var_type
        )

        return s


class _VariableDependencyCollector(lark.Visitor):
    """
    A visitor which is intended to operate *only* on a variable property
    block.  It simply collects all variable names from the block.  These
    are the dependencies of the variable.  Note that there can never be
    indirect dependencies, since variables are never allowed to have property
    blocks, except when they are declared (i.e. no variable inside the block
    can itself have a block).  This makes it really easy: just grab all
    variable names you can find.
    """

    def __init__(self):
        self.variables = set()

    def sdo_ref(self, tree):
        if is_token(tree.children[0], "VARIABLE_NAME"):
            self.variables.add(tree.children[0])


class _VariableProcessor(lark.Transformer):
    """
    Selectively processes just the variable declarations in the parse tree.
    This creates STIX objects for all variables without any dependencies
    (references to other variables in a property block).  For variables with
    dependencies, objects are not created here.  Instead, a placeholder is
    created, and the dependency data is stored in a mapping to keep track of
    it.  Those objects are created later, since they can't be created as they
    are encountered in this parse tree traversal.
    """

    def __init__(self, object_generator):
        """
        Initialize the instance.

        :param object_generator: The object generator which will be used to
            generate values of variables.
        """
        super().__init__()

        self.__object_generator = object_generator

        self.__variables = {}
        self.__objects = {}
        self.__dependencies = {}

    def graph_spec(self, children):
        """
        Callback for the top-level rule in the grammar.  This returns
        variables (mapping from variable name to STIX object ID or
        placeholder), objects (mapping from ID to a STIX object dict), and
        dependencies (mapping from variable name to a set of names of all of
        its dependency variables), as a 3-tuple.
        """
        return self.__variables, self.__objects, self.__dependencies

    def variable_declaration_statement(self, children):
        """
        Updates the variable/object/dependency maps for all variables in the
        statement.
        """
        var_type = children[-1]  # SDO type is always last

        for var_count, var_name, var_props in children[:-1]:

            if var_name in self.__variables:
                raise RedeclaredVariableError(var_name)

            var_dependencies = None

            # Determine if there are any dependency variables
            if var_props:
                var_collector = _VariableDependencyCollector()
                var_collector.visit(var_props)
                var_dependencies = var_collector.variables

            if var_dependencies:
                # If there are dependencies, add a placeholder object to the
                # variables map for now; we need to replace these with actual
                # STIX objects later.  Also store the dependencies for later.
                self.__variables[var_name] = _VariableSpec(
                    var_name, var_count, var_type, var_props
                )
                self.__dependencies[var_name] = var_dependencies

            else:
                # Otherwise, we can directly create an object
                overlay_props = None
                if var_props:
                    builder = _GraphBuilder(
                        self.__object_generator,
                        self.__variables,
                        self.__objects
                    )
                    overlay_props = builder.transform(var_props)

                ids = []
                for _ in range(var_count):
                    obj = _make_object(
                        self.__object_generator, var_type, overlay_props
                    )
                    self.__objects[obj["id"]] = obj
                    ids.append(obj["id"])

                self.__variables[var_name] = ids

        # A formality; no one uses the return value.  But I should probably
        # return something, since all these callbacks are treated as returning
        # a value.
        return None

    def variable_declaration(self, children):
        """
        Produces count/varname/propblock 3-tuples.  The last value (prop block)
        may be None if no property block was given.
        """
        if is_tree(children[0], "count"):
            var_count = int(children[0].children[0])
            var_name = children[1]
        else:
            var_count = 1
            var_name = children[0]

        var_props = None
        if len(children) > 1 and is_tree(children[-1], "property_block"):
            var_props = children[-1]

        # Just forward the property block to the next level up, so we can
        # process the var name, count, type, and prop block together.  (We
        # don't know the variable type at this point, so we can't do anything
        # further here.)
        return var_count, var_name, var_props


class _GraphBuilder(lark.Transformer):
    """
    Selectively processes just the graph statements in a parse tree, and
    produces all of the objects described therein.  No variables are created;
    references to undeclared variables will produce errors.
    """

    def __init__(self, object_generator, variables, objects):
        """
        Initialize this transformer.

        :param object_generator: The object generator to use for making new
            objects.
        :param variables: A mapping from variable name to list of STIX IDs,
            which defines all variables usable in the graph statements.
        :param objects: A mapping from STIX ID to STIX object as dict, which
            contains values for the variables in the variables mapping, and any
            other related objects.  All new objects this transformer creates
            will also be placed in this mapping.
        """
        super().__init__()

        self.__object_generator = object_generator
        self.__variables = variables
        self.__objects = objects

    @lark.v_args(meta=True)
    def graph_statement(self, children, meta):
        """
        Create some objects, optionally connected via a relationship to
        other objects.  Produces the source object IDs only.
        """

        # The below code is simpler if we normalize to a list here, but we
        # still must remember whether this function should propagate a single
        # or list.  So create a new variable instead of modifying source_ids.
        source_ids = children[0]
        if isinstance(source_ids, list):
            source_ids_list = source_ids
        else:
            source_ids_list = [source_ids]

        if len(children) > 1:
            rel_count, rel_type, target_ids = children[1]

            # Same normalization for target IDs.  At least we have the freedom
            # to replace the value of target_ids this time.
            if not isinstance(target_ids, list):
                target_ids = [target_ids]

            for source_id in source_ids_list:

                # Hardcoded special handling of "on": this results in an
                # embedded relationship on the source object whose value is
                # *all* targets, not an SRO per target.  For this reason, it
                # doesn't make sense for the relationship count to be anything
                # but 1.
                if rel_type == "on":
                    if rel_count > 1:
                        raise LanguageError(
                            "Relationship 'on' must have count 1", meta
                        )
                    source_obj = self.__objects[source_id]
                    source_obj["object_refs"] = target_ids

                else:
                    for target_id in target_ids:
                        for _ in range(rel_count):
                            rel = _make_sro(
                                self.__object_generator,
                                source_id,
                                rel_type.value,
                                target_id
                            )
                            self.__objects[rel["id"]] = rel

        return source_ids

    def relationship(self, children):
        """
        Produce a rel_count, rel, target_ids triple representing most of a
        relationship (it doesn't include the source object(s))
        """

        if isinstance(children[0], int):
            rel_count, rel_type, target_ids = children
        else:
            rel_count = 1
            rel_type, target_ids = children

        return rel_count, rel_type, target_ids

    def sdo_list(self, children):
        """
        Produces the concatenation of all STIX object IDs in child nodes
        in a single list.
        """
        all_children = []
        for child in children:
            if isinstance(child, list):
                all_children.extend(child)
            else:
                all_children.append(child)

        return all_children

    def sdo_ref(self, children):
        """
        Produces a single or list of STIX object IDs, either from a
        referenced variable, or from newly created objects.
        """
        if is_token(children[0], "VARIABLE_NAME"):
            # ref is a variable
            var_name = children[0]
            if var_name in self.__variables:
                ids = self.__variables[var_name]
            else:
                raise UndeclaredVariableError(var_name)
        else:
            # ref is to inline SDO(s)
            ids = children[0]

        # A variable or inline SDO with count=1 will produce a single value;
        # count > 1 produces a list.  We need to propagate the right thing,
        # so that STIX properties which expect single IDs don't get lists.
        # (One wishes that such properties would accept a length-1 list, but
        # they don't.)
        if len(ids) == 1:
            ids = ids[0]

        return ids

    def sdo_inline(self, children):
        """Produces a list of the new STIX object IDs."""
        if isinstance(children[0], int):
            count = children[0]
            sdo_type = children[1]
        else:
            count = 1
            sdo_type = children[0]

        overlay_props = None
        if len(children) > 1 and isinstance(children[-1], dict):
            overlay_props = children[-1]

        ids = []
        for _ in range(count):
            obj = _make_object(self.__object_generator, sdo_type, overlay_props)
            self.__objects[obj["id"]] = obj
            ids.append(obj["id"])

        return ids

    def count(self, children):
        """Produces the count, as an int"""
        return int(children[0])

    def property_block(self, children):
        """
        Produces a mapping from prop name to ID(s) or other string literals,
        from the property block.
        """

        overlay_props = {}
        for prop_name, value in children:
            if is_token(value, "ESCAPED_STRING"):
                value = _string_token_value(value)

            overlay_props[prop_name] = value

        return overlay_props

    def property_assignment(self, children):
        """
        Propagates its children.  This will produce a 2-item list including
        the property name and a single or list of STIX IDs which are the "top"
        of the object graph which is the property value.
        """
        return children

    def string_array(self, children):
        """
        Produces a list of strings from the array.
        """
        values = [
            _string_token_value(tok)
            for tok in children
        ]

        return values

    @lark.v_args(meta=True)
    def sighting(self, children, meta):
        """
        Creates a sighting object (and all other related objects).
        """
        sighting_of = overlay_props = None

        if len(children) == 1:
            if isinstance(children[0], dict):
                overlay_props = children[0]
                sighting_of = None
            else:
                overlay_props = None
                sighting_of = children[0]

        elif len(children) > 1:
            overlay_props = children[0]
            sighting_of = children[1]

        if sighting_of and overlay_props and "sighting_of_ref" in overlay_props:
            raise LanguageError(
                "property 'sighting_of_ref' can't both be given explicitly and "
                "in the property block",
                meta
            )

        obj = _make_sighting(
            self.__object_generator, sighting_of, overlay_props
        )
        self.__objects[obj["id"]] = obj

        # A formality; no one uses the return value.  But I should probably
        # return something, since all these callbacks are treated as returning
        # a value.
        return None


class LanguageProcessor:
    """
    Instances process stix prototyping language, and produce stix objects.
    """
    def __init__(self, object_generator, stix_version="2.1"):
        """
        Initialize this processor.

        :param object_generator: The object generator to use
        :param stix_version: Which version of STIX to use.
        :raises stix2generator.exceptions.RegistryNotFoundError: If there isn't
            a built-in registry for the given STIX version
        :raises IOError: (python 2) If the registry JSON file couldn't be opened
            or read
        :raises OSError: (python 3) If the registry JSON file couldn't be opened
            or read (IOError is retained as an alias for backward
            compatibility).
        """
        self.__object_generator = object_generator
        self.__stix_version = stix_version

    def build_graph(
        self, graph_spec, return_variable_bindings=False,
        embed_variable_names=False
    ):
        """
        Build STIX objects from the given specification, expressed with the
        STIX prototyping language.

        :param graph_spec: The graph specification
        :param return_variable_bindings: Whether the caller wants the variable
            bindings returned
        :param embed_variable_names: Whether variable names should be embedded
            in generated objects bound to a variable, using a custom property
        :return: If return_variable_bindings is False, a list of STIX objects.
            Otherwise, return a 2-tuple where the first item is the list of
            generated objects, and the second is a mapping from variable name
            to list of STIX IDs.  This latter value represents the variable
            bindings.
        :raises stix2generator.builder.LanguageError: If there are any errors
            processing the specification itself
        :raises stix2generator.make_object.ObjectGenerationError: If there is an
            error randomly generating a STIX object
        :raises stix2.exceptions.STIXError: If the objects and/or relationships
            expressed in the language, aren't valid STIX
        """
        logger = _get_logger()

        parse_tree = _parser.parse(graph_spec)

        if logger.isEnabledFor(stix2generator.logging.EXTRA_VERBOSE):
            logger.log(stix2generator.logging.EXTRA_VERBOSE, "Parse tree:")
            _print_parse_tree(logger, parse_tree)

        variables, objects, dependencies = \
            _VariableProcessor(self.__object_generator).transform(parse_tree)

        if dependencies:
            self.__process_variable_dependencies(
                variables, objects, dependencies
            )

        if variables and logger.isEnabledFor(logging.DEBUG):
            logger.debug("Variables:")
            for var, ids in variables.items():
                logger.debug("%s = %s", var, ids)

        # This is necessary so that GraphBuilder doesn't re-visit property
        # blocks in variable declarations, and erroneously create extra objects.
        _remove_variable_declaration_statements(parse_tree)

        graph_builder = _GraphBuilder(
            self.__object_generator, variables, objects
        )
        graph_builder.transform(parse_tree)

        # Embed variable names if requested
        if embed_variable_names:
            for var, ids in variables.items():
                for id_ in ids:
                    objects[id_][_VARIABLE_NAME_PROPERTY] = var.value

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Objects:")
            for obj in objects.values():
                logger.debug(pprint.pformat(obj))

        stix_objs = [
            stix2.parse(
                stix_dict, version=self.__stix_version, allow_custom=True
            )
            for stix_dict in objects.values()
        ]

        if return_variable_bindings:
            # The internal variables mapping is keyed by tokens; I don't think
            # that makes sense for users.  So make a new map keyed by plain
            # string variable names.
            variables_plain_names = {
                var.value: ids
                for var, ids in variables.items()
            }
            ret = stix_objs, variables_plain_names
        else:
            ret = stix_objs

        return ret

    def __process_variable_dependencies(self, variables, objects, dependencies):
        """
        Create values for all variables with dependencies.

        :param variables: A mapping with any already-initialized variables, and
            all of the VariableSpec placeholders which were created.  This will
            be updated with newly created variables.
        :param objects: A mapping to store all newly created objects in.
        :param dependencies: The dependency data, as a mapping from var name to
            a set of dependencies.  (This is basically an adjacency list
            representation of a directed graph.)
        :raises UndeclaredVariableError: If there are any references to
            undeclared variables
        :raises CircularVariableDependenciesError: If circular dependencies are
            encountered
        """

        logger = _get_logger()

        sorted_var_names = _topo_sort_dependencies(dependencies)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Variable creation order: %s",
                ", ".join(tok.value for tok in sorted_var_names)
            )

        for var_name in sorted_var_names:

            if var_name not in variables:
                raise UndeclaredVariableError(var_name)

            var_spec = variables[var_name]

            # Our "leaf node" variables will be regular ones, not
            # VariableSpec's; we don't need to do anything for those.
            if not isinstance(var_spec, _VariableSpec):
                continue

            builder = _GraphBuilder(self.__object_generator, variables, objects)
            overlay_props = builder.transform(var_spec.var_props_tree)

            ids = []
            for _ in range(var_spec.var_count):
                obj = _make_object(
                    self.__object_generator, var_spec.var_type, overlay_props
                )
                ids.append(obj["id"])
                objects[obj["id"]] = obj

            # Now we can replace the spec with real IDs
            variables[var_name] = ids

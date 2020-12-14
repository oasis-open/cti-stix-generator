import argparse
import math

import stix2generator
import stix2generator.generation.object_generator
import stix2generator.generation.reference_graph_generator
import stix2generator.generation.stix_generator
import stix2generator.logging
import stix2generator.utils


def nonnegative_int(arg):
    """
    Verify/convert arg to a non-negative integer.

    :param arg: A commandline arg as a string
    :return: The integer
    :raises argparse.ArgumentTypeError: If the arg can't be converted or is
        out of range
    """
    try:
        int_arg = int(arg)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            "Not a nonnegative integer: {}".format(arg)
        ) from e

    if int_arg < 0:
        raise argparse.ArgumentTypeError(
            "Not a nonnegative integer: {}".format(arg)
        )

    return int_arg


def positive_int(arg):
    """
    Verify/convert arg to a positive integer.

    :param arg: A commandline arg as a string
    :return: The integer
    :raises argparse.ArgumentTypeError: If the arg can't be converted or is
        out of range
    """
    try:
        int_arg = int(arg)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            "Not a positive integer: {}".format(arg)
        ) from e

    if int_arg < 1:
        raise argparse.ArgumentTypeError(
            "Not a positive integer: {}".format(arg)
        )

    return int_arg


def probability(arg):
    """
    Verify/convert arg to a probability value in the range [0, 1].

    :param arg: A commandline arg as a string
    :return: The probability as a float
    :raises argparse.ArgumentTypeError: If the arg can't be converted or is
        out of range
    """
    try:
        float_arg = float(arg)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            "Not a float in [0,1]: {}".format(arg)
        ) from e

    if math.isnan(float_arg) or not 0 <= float_arg <= 1:
        raise argparse.ArgumentTypeError(
            "Not a float in [0,1]: {}".format(arg)
        )

    return float_arg


def parse_args():
    arg_parser = argparse.ArgumentParser(
        description="Generation random STIX content"
    )

    arg_parser.add_argument(
        "--min-rels",
        help="""Minimum number of SROs to create.  Default=%(default)d""",
        type=positive_int,
        default=1
    )

    arg_parser.add_argument(
        "--max-rels",
        help="""Maximum number or SROs to create.  Default=%(default)d""",
        type=positive_int,
        default=5
    )

    arg_parser.add_argument(
        "--p-reuse",
        help="""
        Probability of object reuse, when creating new connections among
        objects.  Must be a real number in [0, 1].  Lower values result in a
        graph with more nodes and less interconnection.  Higher values result
        in a graph with fewer nodes and more interconnection.
        Default=%(default).1f
        """,
        type=probability,
        default=0.5
    )

    arg_parser.add_argument(
        "--p-sighting",
        help="""
        Probability that when an SRO is added, it is a sighting.  Must be a
        real number in [0, 1].  Default=%(default).1f
        """,
        type=probability,
        default=0.1
    )

    arg_parser.add_argument(
        "--dangling-refs",
        help="""
        Leave reference properties "dangling".  Don't force them to refer to
        existing objects.  Applies to all reference properties *except* the
        endpoints of SROs.
        """,
        action="store_true"
    )

    arg_parser.add_argument(
        "--ref-max-depth",
        help="""
        If creating a new object to avoid a dangling reference, the new object
        could itself have reference properties; new objects created to satisfy
        those could themselves have reference properties, etc.  This setting
        limits how far we grow this "reference graph".  Enforcement of this
        limit is best-effort; reference properties required by the
        specification may cause further growth.  Only applicable if
        --dangling-refs is not given.  Must be a non-negative integer.
        Default=%(default)d
        """,
        type=nonnegative_int,
        default=0
    )

    arg_parser.add_argument(
        "-v", "--verbose",
        help="""
        Enable verbose diagnostic output.  Repeat for
        increased verbosity.
        """,
        action="count"
    )

    arg_parser.add_argument(
        "--stix-version",
        help="STIX version to use.  Default=%(default)s",
        choices=["2.0", "2.1"],
        default="2.1"
    )

    arg_parser.add_argument(
        "-b", "--bundle",
        help="Create a bundle",
        action="store_true"
    )

    args = arg_parser.parse_args()

    return args


def main():
    args = parse_args()

    stix2generator.logging.config_logging(args.verbose)

    obj_gen_config = stix2generator.generation.object_generator.Config(
        # hard-code; we need this disabled for ref graph max-depth setting
        # to mean anything.
        minimize_ref_properties=False
    )

    ref_gen_config = stix2generator.generation.reference_graph_generator.Config(
        max_depth=args.ref_max_depth,
        probability_reuse=args.p_reuse
    )

    stix_gen_config = stix2generator.generation.stix_generator.Config(
        min_relationships=args.min_rels,
        max_relationships=args.max_rels,
        probability_reuse=args.p_reuse,
        probability_sighting=args.p_sighting,
        complete_ref_properties=not args.dangling_refs
    )

    stix_gen = stix2generator.create_stix_generator(
        object_generator_config=obj_gen_config,
        ref_graph_generator_config=ref_gen_config,
        stix_generator_config=stix_gen_config,
        stix_version=args.stix_version
    )

    graph = stix_gen.generate()

    if args.bundle:
        bundle = stix2generator.utils.make_bundle(
            list(graph.values()), args.stix_version
        )

        print(bundle.serialize(pretty=True))

    else:
        for obj in graph.values():
            print(obj.serialize(pretty=True))


if __name__ == "__main__":
    main()

import argparse
import configparser
import json

import stix2generator
import stix2generator.language.builder
import stix2generator.generation.object_generator
import stix2generator.logging


def parse_args():
    arg_parser = argparse.ArgumentParser(
        description="""Create STIX content from the STIX prototyping language"""
    )

    arg_parser.add_argument("language-file",
                            help="""
                            The file containing STIX prototyping language
                            """
                            )
    arg_parser.add_argument("-b", "--bundle",
                            help="Create a bundle",
                            action="store_true"
                            )
    arg_parser.add_argument("-e", "--encoding",
                            help="""
                            Encoding to use when reading text files, e.g.
                            STIX prototyping language, custom generator
                            specifications, etc.  Default=%(default)s
                            """,
                            default="utf-8"
                            )
    arg_parser.add_argument("-v", "--verbose",
                            help="""
                            Enable verbose diagnostic output.  Repeat for
                            increased verbosity.
                            """,
                            action="count"
                            )
    arg_parser.add_argument("--stix-version",
                            help="STIX version to use.  Default=%(default)s",
                            choices=["2.0", "2.1"],
                            default="2.1"
                            )
    arg_parser.add_argument("--extra-specs",
                            help="""A JSON file with extra object generator
                            specifications.  These will be merged with the
                            built-in specifications, and made available for use
                            in prototyping language content.
                            """
                            )
    arg_parser.add_argument("-n", "--embed-variable-names",
                            help="""Embed variable names in generated objects
                            using a custom property.
                            """,
                            action="store_true"
                            )
    arg_parser.add_argument("-c", "--config",
                            help="""Config file with options to customize how
                            content is generated.
                            """,
                            )

    args = arg_parser.parse_args()
    return args


def main():
    args = parse_args()

    stix2generator.logging.config_logging(args.verbose)

    proto_lang_file = getattr(args, "language-file")
    with open(proto_lang_file, "r", encoding=args.encoding) as f:
        proto_lang = f.read()

    extra_specs = None
    if args.extra_specs:
        with open(args.extra_specs, "r", encoding=args.encoding) as f:
            extra_specs = json.load(f)

    tmp_config = {}
    if args.config:
        config_parser = configparser.SafeConfigParser()
        config_parser.read(args.config)
        tmp_config = config_parser['main']

    generator_config = stix2generator.generation.object_generator.Config(
        **tmp_config
    )

    processor = stix2generator.create_default_language_processor(
        generator_config, extra_specs, args.stix_version
    )
    stix_objs = processor.build_graph(
        proto_lang, embed_variable_names=args.embed_variable_names
    )

    if args.bundle:
        bundle = stix2generator.utils.make_bundle(
            stix_objs, args.stix_version
        )

        print(bundle.serialize(pretty=True))

    else:
        for obj in stix_objs:
            print(obj.serialize(pretty=True))


if __name__ == "__main__":
    main()

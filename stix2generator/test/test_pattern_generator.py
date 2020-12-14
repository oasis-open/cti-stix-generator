import pytest
import re
import stix2generator
from stix2generator.generation.pattern_generator import PatternGenerator, Config
import stix2patterns.inspector
from stix2patterns.validator import validate
from stix2patterns.v21.pattern import Pattern


_REPEATS_RE = re.compile(r"REPEATS (\d+) TIMES")
_WITHIN_RE = re.compile(r"WITHIN (\d+) SECONDS")


@pytest.fixture(scope="session")
def default_object_generator():
    return stix2generator.create_object_generator(stix_version="2.1")


def test_patterns_valid(num_trials, default_object_generator):
    generator = PatternGenerator(default_object_generator, "2.1")
    for _ in range(num_trials):
        pattern = generator.generate()

        # Turn on error printing so that we can see what the errors are
        # just by changing how we invoke pytest.
        assert validate(pattern, stix_version="2.1", print_errs=True)


def test_config_pattern_size(num_trials, default_object_generator):
    pattern_config = Config(min_pattern_size=3, max_pattern_size=7)
    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        comparison_data = pattern_data.comparisons
        pattern_size = sum(
            len(comparisons)
            for comparisons in comparison_data.values()
        )

        assert 3 <= pattern_size <= 7


def test_config_repeat_count(num_trials, default_object_generator):
    pattern_config = Config(
        min_repeat_count=3,
        max_repeat_count=7,
        # Ensure there are lots of qualifiers, to increase the probability we
        # will actually see some REPEATS qualifiers to test.  There's not
        # actually any guarantee any will show up in the pattern!
        # ("probability_qualifier=1" below guarantees some qualifiers will be
        # included, but not which type of qualifiers they are.)
        min_pattern_size=5,
        max_pattern_size=10,
        probability_qualifier=1,
    )
    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        for qualifier in pattern_data.qualifiers:
            m = _REPEATS_RE.match(qualifier)
            if m:
                repeat_count = int(m.group(1))
                assert 3 <= repeat_count <= 7


def test_config_within_count(num_trials, default_object_generator):
    pattern_config = Config(
        min_within_count=3,
        max_within_count=7,
        min_pattern_size=5,
        max_pattern_size=10,
        probability_qualifier=1,
    )
    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        for qualifier in pattern_data.qualifiers:
            m = _WITHIN_RE.match(qualifier)
            if m:
                within_count = int(m.group(1))
                assert 3 <= within_count <= 7


def test_config_continue_path_through_ref_always(
    num_trials, default_object_generator
):
    pattern_config = Config(
        min_pattern_size=5,
        max_pattern_size=10,
        probability_continue_path_through_ref=1,
    )

    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        for comparisons in pattern_data.comparisons.values():
            for path, _, _ in comparisons:
                # If all paths continue through refs, a ref prop can't be last,
                # and a refs prop can't be second-to-last.
                path_len = len(path)
                for i, path_elt in enumerate(path):
                    if isinstance(path_elt, str):
                        assert not path_elt.endswith("_ref") or i < path_len-1
                        assert not path_elt.endswith("_refs") or i < path_len-2


def test_config_continue_path_through_ref_never(
    num_trials, default_object_generator
):
    pattern_config = Config(
        min_pattern_size=5,
        max_pattern_size=10,
        probability_continue_path_through_ref=0,
    )

    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        for comparisons in pattern_data.comparisons.values():
            for path, _, _ in comparisons:
                # If no paths continue through refs, a ref prop must be last,
                # and a refs prop must be second-to-last.
                path_len = len(path)
                for i, path_elt in enumerate(path):
                    if isinstance(path_elt, str):
                        if path_elt.endswith("_ref"):
                            assert i == path_len-1
                        elif path_elt.endswith("_refs"):
                            assert i == path_len-2


def test_config_probability_index_star_step_always(
        num_trials, default_object_generator
):
    pattern_config = Config(
        min_pattern_size=5,
        max_pattern_size=10,
        probability_index_star_step=1,
    )

    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        for comparisons in pattern_data.comparisons.values():
            for path, _, _ in comparisons:
                # If always using index star steps, there should never be any
                # integer steps.
                assert not any(
                    isinstance(path_elt, int) for path_elt in path
                )


def test_config_probability_index_star_step_never(
        num_trials, default_object_generator
):
    pattern_config = Config(
        min_pattern_size=5,
        max_pattern_size=10,
        probability_index_star_step=0,
    )

    generator = PatternGenerator(
        default_object_generator, "2.1", pattern_config
    )

    for _ in range(num_trials):
        pattern_str = generator.generate()
        pattern_obj = Pattern(pattern_str)
        pattern_data = pattern_obj.inspect()

        for comparisons in pattern_data.comparisons.values():
            for path, _, _ in comparisons:
                # If always using integer steps into lists, there should never
                # be any star steps.
                assert not any(
                    path_elt is stix2patterns.inspector.INDEX_STAR
                    for path_elt in path
                )

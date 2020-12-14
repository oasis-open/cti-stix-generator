def test_null(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "null"
        })

        assert value is None

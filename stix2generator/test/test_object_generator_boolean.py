def test_boolean(object_generator, num_trials):
    for _ in range(num_trials):
        value = object_generator.generate_from_spec({
            "type": "boolean"
        })

        assert value in (True, False)

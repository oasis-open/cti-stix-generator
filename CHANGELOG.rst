CHANGELOG
=========


0.2.0 - Released 2021-07-14
---------------------------

* Miscellaneous registry updates
* Bring stix-generator back to compatibility with the stix2 library
* Add new infrastructure-type-ov values , Incident object for CS03
* Use real values for path_enc
* Add Artifact.decryption_key co-constraint
* Add shortcuts for TLP markings to default registry
* Change the STIX timestamp semantic for the object generator to
    generate timestamps with at least millisecond precision.
    Coconstraint satisfaction is changed to be done at full microsecond
    precision.  So if "ts1 > ts2", ts1 could be as little as one
    microsecond larger than t2.
* Change version-related property specs of malware-analysis SDO spec to generate strings
* Pass the SCO type enum into generate() directly instead of
    manually picking a specific type first.  The generate()
    implementation handles type selection automatically!
* Add a "parse" setting to STIXGenerator's config, to enable/disable
    parsing to stix2 objects, analogously to the change to
    ReferenceGraphGenerator.
* Fix the observable-container semantic to switch off parsing
    in its ReferenceGraphGenerator instance, to ensure generated
    objects are plain JSON-serializable values.


0.1.0 - Released 2020-12-13
---------------------------

* Initial public version.

import collections


# Summary of defined SROs.  This basically shows how STIX types are allowed to
# relate to each other, and via which relationship types.
#
# Hopefully this is an easy structure to maintain: maps relationship source
# STIX type to a map from relationship type to a list of target types.  It
# eliminates repetition in source and relationship types.
_RELATIONSHIPS = {
    "attack-pattern": {
        "delivers": ["malware"],
        "targets": ["identity", "location", "vulnerability"],
        "uses": ["malware", "tool"]
    },
    "campaign": {
        "attributed-to": ["intrusion-set", "threat-actor"],
        "compromises": ["infrastructure"],
        "originates-from": ["location"],
        "targets": ["identity", "location", "vulnerability"],
        "uses": ["attack-pattern", "infrastructure", "malware", "tool"]
    },
    "course-of-action": {
        "investigates": ["indicator"],
        "mitigates": [
            "attack-pattern", "indicator", "malware", "tool", "vulnerability"
        ]
    },
    "identity": {
        "located-at": ["location"]
    },
    "indicator": {
        "indicates": [
            "attack-pattern", "campaign", "infrastructure", "intrusion-set",
            "malware", "threat-actor", "tool"
        ],
        "based-on": ["observed-data"]
    },
    "infrastructure": {
        "communicates-with": [
            "infrastructure", "ipv4-addr", "ipv6-addr", "domain-name", "url"
        ],
        "consists-of": [
            "infrastructure", "observed-data",
            # all generatable SCO types
            "artifact", "autonomous-system", "directory", "domain-name",
            "email-addr", "email-message", "file", "ipv4-addr", "ipv6-addr",
            "mac-addr", "mutex", "network-traffic", "process", "software",
            "url", "user-account", "windows-registry-key", "x509-certificate"
        ],
        "controls": ["infrastructure", "malware"],
        "delivers": ["malware"],
        "has": ["vulnerability"],
        "hosts": ["tool", "malware"],
        "located-at": ["location"],
        "uses": ["infrastructure"],
    },
    "intrusion-set": {
        "attributed-to": ["threat-actor"],
        "compromises": ["infrastructure"],
        "hosts": ["infrastructure"],
        "owns": ["infrastructure"],
        "originates-from": ["location"],
        "targets": ["identity", "location", "vulnerability"],
        "uses": ["attack-pattern", "infrastructure", "malware", "tool"]
    },
    "malware": {
        "authored-by": ["threat-actor", "intrusion-set"],
        "beacons-to": ["infrastructure"],
        "exfiltrate-to": ["infrastructure"],
        "communicates-with": ["ipv4-addr", "ipv6-addr", "domain-name", "url"],
        "controls": ["malware"],
        "downloads": ["malware", "tool", "file"],
        "drops": ["malware", "tool", "file"],
        "exploits": ["vulnerability"],
        "originates-from": ["location"],
        "targets": ["identity", "infrastructure", "location", "vulnerability"],
        "uses": ["attack-pattern", "infrastructure", "malware", "tool"],
        "variant-of": ["malware"],
    },
    "malware-analysis": {
        "characterizes": ["malware"],
        "analysis-of": ["malware"],
        "static-analysis-of": ["malware"],
        "dynamic-analysis-of": ["malware"]
    },
    "threat-actor": {
        "attributed-to": ["identity"],
        "compromises": ["infrastructure"],
        "hosts": ["infrastructure"],
        "owns": ["infrastructure"],
        "impersonates": ["identity"],
        "located-at": ["location"],
        "targets": ["identity", "location", "vulnerability"],
        "uses": ["attack-pattern", "infrastructure", "malware", "tool"]
    },
    "tool": {
        "delivers": ["malware"],
        "drops": ["malware"],
        "has": ["vulnerability"],
        "targets": ["identity", "infrastructure", "location", "vulnerability"]
    }
}


# Programmatically add some common relationships, to reduce verbosity in
# the _RELATIONSHIPS map
for src_type, rel_info in _RELATIONSHIPS.items():
    rel_info["derived-from"] = [src_type]
    rel_info["duplicate-of"] = [src_type]


# Omit "related-to".  Currently special-casing that in the STIX generator.


Relationship = collections.namedtuple(
    "Relationship", "src_type, rel_type, target_type"
)


# A structure to make it easy to choose a graph edge based on the type of node
# it needs to connect to at one end.
RELATIONSHIP_OBJECTS_BY_ENDPOINT_TYPE = {}


for src_type, rel_info in _RELATIONSHIPS.items():
    for rel_type, target_types in rel_info.items():
        for target_type in target_types:

            rel_obj = Relationship(src_type, rel_type, target_type)

            RELATIONSHIP_OBJECTS_BY_ENDPOINT_TYPE.setdefault(
                src_type, []
            ).append(rel_obj)

            RELATIONSHIP_OBJECTS_BY_ENDPOINT_TYPE.setdefault(
                target_type, []
            ).append(rel_obj)

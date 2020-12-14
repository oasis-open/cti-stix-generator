|Build_Status| |Coverage| |Version|

cti-stix-generator
==================

This is an `OASIS TC Open Repository
<https://www.oasis-open.org/resources/open-repositories/>`__. See the
`Governance <#governance>`__ section for more information.

The STIX generator is a tool for generating random STIX content for prototyping
and testing. It uses a simple, sentence-like syntax for expressing what STIX
content to generate. This tool is provided in two forms: as a Jupyter notebook
and as a commandline tool.

For more information, see `the documentation <https://stix2-generator.readthedocs.io/>`__ on ReadTheDocs.

Jupyter Notebook
----------------

The `Jupyter notebook <https://jupyter.org/>`__ provides an interactive
environment to input generator syntax and view the generated content. To use
the notebook, install the generator's dependencies including the ``jupyter``
extras, and run Jupyter:

.. code-block:: bash

    pip install -e .[jupyter]
    jupyter nbextension install stix2viz --py
    jupyter nbextension enable stix2viz --py
    jupyter notebook

Open ``stix.ipynb`` in Jupyter to use the tool. Look at ``examples.ipynb`` for
documentation and examples of the syntax.

Commandline Tool
----------------

The commandline version of the tool reads prototyping language from a file, and
prints the generated objects to stdout.  If a bundle is selected, the bundle is
printed instead.

.. code-block::

    usage: build_stix.py [-h] [-b] [-e ENCODING] [-v] [--stix-version {2.0,2.1}]
                         [--extra-specs EXTRA_SPECS] [-m]
                         language-file

    Create STIX content from the STIX prototyping language

    positional arguments:
      language-file         The file containing STIX prototyping language

    optional arguments:
      -h, --help            show this help message and exit
      -b, --bundle          Create a bundle
      -e ENCODING, --encoding ENCODING
                            Encoding to use when reading text files, e.g. STIX
                            prototyping language, custom generator specifications,
                            etc. Default=utf-8
      -v, --verbose         Enable verbose diagnostic output. Repeat for increased
                            verbosity.
      --stix-version {2.0,2.1}
                            STIX version to use. Default=2.1
      --extra-specs EXTRA_SPECS
                            A JSON file with extra object generator
                            specifications. These will be merged with the built-in
                            specifications, and made available for use in
                            prototyping language content.
      -m, --minimize-refs   Minimize reference properties in generated objects
                            (*_ref and *_refs).

Caveats
-------

The tool generates random data for all properties, so it may be nonsensical but
will have the correct datatype or structure according to the STIX
specification.

The object generator currently only generates STIX 2.1 objects. The commandline
tool and some APIs will error out if any STIX version other than "2.1" is used.

Governance
----------

This GitHub public repository `cti-stix-generator <https://github.com/oasis-open/cti-stix-generator/>`__ was created at the request of the `OASIS Cyber Threat Intelligence (CTI) TC <https://www.oasis-open.org/committees/cti/>`__as an `OASIS TC Open Repository <https://www.oasis-open.org/resources/open-repositories/>`__ to support development of open source resources related to Technical Committee work.

While this TC Open Repository remains associated with the sponsor TC, its development priorities, leadership, intellectual property terms, participation rules, and other matters of governance are `separate and distinct <https://github.com/oasis-open/cti-stix-generator/blob/master/CONTRIBUTING.md#governance-distinct-from-oasis-tc-process>`__ from the OASIS TC Process and related policies.

All contributions made to this TC Open Repository are subject to open source license terms expressed in the `BSD-3-Clause License <https://www-legacy.oasis-open.org/sites/www.oasis-open.org/files/BSD-3-Clause.txt>`__. That license was selected as the declared `applicable license <https://www.oasis-open.org/resources/open-repositories/licenses>`__ when the TC Open Repository was created.

As documented in `Public Participation Invited <https://github.com/oasis-open/cti-stix-generator/blob/master/CONTRIBUTING.md#public-participation-invited>`__, contributions to this OASIS TC Open Repository are invited from all parties, whether affiliated with OASIS or not. Participants must have a GitHub account, but no fees or OASIS membership obligations are required. Participation is expected to be consistent with the `OASIS TC Open Repository Guidelines and Procedures <https://www.oasis-open.org/policies-guidelines/open-repositories>`__, the open source `LICENSE <https://github.com/oasis-open/cti-stix-generator/blob/master/LICENSE.md>`__ designated for this particular repository, and the requirement for an `Individual Contributor License Agreement <https://www.oasis-open.org/resources/open-repositories/cla/individual-cla>`__ that governs intellectual property.

Maintainers
~~~~~~~~~~~

TC Open Repository `Maintainers <https://www.oasis-open.org/resources/open-repositories/maintainers-guide>`__ are responsible for oversight of this project's community development activities, including evaluation of GitHub `pull requests <https://github.com/oasis-open/cti-stix-generator/blob/master/CONTRIBUTING.md#fork-and-pull-collaboration-model>`__ and `preserving <https://www.oasis-open.org/policies-guidelines/open-repositories#repositoryManagement>`__ open source principles of openness and fairness. Maintainers are recognized and trusted experts who serve to implement community goals and consensus design preferences.

Initially, the TC members have designated one or more persons to serve as Maintainer(s); subsequently, participating community members may select additional or substitute Maintainers, by `consensus agreements <https://www.oasis-open.org/resources/open-repositories/maintainers-guide#additionalMaintainers>`__.

.. _currentmaintainers:

Current Maintainers of this TC Open Repository
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

-  `Chris Lenk <mailto:clenk@mitre.org>`__; GitHub ID: `clenk <https://github.com/clenk/>`__; WWW: `MITRE Corporation <http://www.mitre.org/>`__

-  `Andy Chisholm <mailto:chisholm@mitre.org>`__; GitHub ID: `chisholm <https://github.com/chisholm/>`__; WWW: `MITRE Corporation <http://www.mitre.org/>`__

About OASIS TC Open Repositories
--------------------------------

-  `TC Open Repositories: Overview and Resources <https://www.oasis-open.org/resources/open-repositories/>`__
-  `Frequently Asked Questions <https://www.oasis-open.org/resources/open-repositories/faq>`__
-  `Open Source Licenses <https://www.oasis-open.org/resources/open-repositories/licenses>`__
-  `Contributor License Agreements (CLAs) <https://www.oasis-open.org/resources/open-repositories/cla>`__
-  `Maintainers' Guidelines and Agreement <https://www.oasis-open.org/resources/open-repositories/maintainers-guide>`__

Feedback
--------

Questions or comments about this TC Open Repository's activities should be composed as GitHub issues or comments. If use of an issue/comment is not possible or appropriate, questions may be directed by email to the Maintainer(s) `listed above <#currentmaintainers>`__.

Please send general questions about TC Open Repository participation to OASIS Staff at repository-admin@oasis-open.org and any specific CLA-related questions to repository-cla@oasis-open.org.

.. |Build_Status| image:: https://api.travis-ci.com/oasis-open/cti-stix-generator.svg?branch=master
   :target: https://travis-ci.com/oasis-open/cti-stix-generator
.. |Coverage| image:: https://codecov.io/gh/oasis-open/cti-stix-generator/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/oasis-open/cti-stix-validator
.. |Version| image:: https://img.shields.io/pypi/v/stix2-generator.svg?maxAge=3600
   :target: https://pypi.org/project/stix2-generator/

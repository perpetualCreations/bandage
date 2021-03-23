Update Patching for Python 3
=====================================
:Latest Version - |version|:

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Indices and tables
------------------
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* `Back to Projects </index.html##projects>`_

Install
-------
Bandage is available on PyPI or as a wheel file for manual installation. Install through PIP.

.. code-block:: bash

   pip install bandage

.. parsed-literal::

   wget https://github.com/perpetualCreations/bandage/releases/download/\ |release|\ /bandage-\ |release|\ -py3-none-any.whl
   pip install /path/to/wheel/file/bandage-\ |release|\ -py3-none-any.whl

.. |release| replace:: |version|

As listed in the requirements MANIFEST, it depends on urllib3. If this dependency has not already been installed, use PIP again.

.. code-block:: bash

   pip install urllib3

Examples
--------
Bandage has three classes: Patcher, Weave, and Supply, which are for apply, generating, and finding patches respectively.
They are structured as factory methods.

.. code-block:: python

   import bandage
   weaver = bandage.Weave(
   "/path/to/old/release/archive/old.zip",
   "/path/to/new/release/archive/new.zip",
   "/path/to/dir/for/patch/to/be/dumped/to/"
   ) # the old/new release archives can be referenced as HTTPS/HTTP URLs
     # this will create a patch archive under the third listed path

   patcher = bandage.Patcher(
   "/path/to/patch/file/patch.zip",
   "/path/to/target/dir/"
   ) # the patch file can be referenced as a HTTPS/HTTP URL, like Weave

   supplier = bandage.Supply(
   "https://example.com/bandage_remote/",
   "/path/to/current/version/file/"
   ) # see Remotes section for more information about remotes,
     # second path to VERSION header file should be of target
   results = supplier.realize() # returns list,
   # index 0 is int -1 to 1, -1 being an update available,
   # 0 being target is up-to-date, and 1 being no valid available patches were found
   # index 1 is a Union[str, None], is None if index 0 is 0 or 1,
   # if -1 is a str containing URL to best patch file for updating

See Bandage API reference for more usage documentation.

Remotes
-------
As mentioned in the API reference for bandage.Supply, there are two options for valid remotes.

* Github releases tagged "BANDAGE" in all caps (i.e. https://github.com/perpetualCreations/bandage/releases/tag/BANDAGE).
* Any normal web server with BANDAGE headers.

Regardless of which of the two options you choose, two header files are required, BANDAGE_LINEAGE and BANDAGE_PATCHES.
BANDAGE_LINEAGE contains a list of release versions, formatted,

.. code-block::

   v1.0
   v0.9
   v0.8b
   v0.8a
   v0.8

...Where each line is its own version number. Versions should be ordered latest to oldest, line 0 being the latest version.

BANDAGE_PATCHES contains a list of available patches, formatted,

.. code-block::

   v0.8b -> v0.9||patch_file.zip
   v0.8a -> v0.8b||/untested/patch_file_2.zip
   v0.9 -> v1.0||https://108be2d78c28daae70b29d2edd07bb3b4a3c05dc3020b87e969403a8aedb27a8.net/bandage/external_patch.zip

...Where each line specifies a source (upgrading from) and destination (upgrading to) version, separated by two pipe characters the name of the patch file.
The patch file "name" can also specify a directory above the supplied remote URL, or set to be referenced through another URL address (unavailable for Github BANDAGE release distribution).
The order in which patch files are recorded does not matter. It is recommended to put more frequently used patches higher up in the list, to speed up bandage.Supply parsing.

If using the first option (a Github release), the header files should be placed in the release contents, alongside patch files specified in BANDAGE_PATCHES.
Please note bandage.Supply does not accept any release tags other than BANDAGE (i.e. /releases/latest/ and /releases/tag/x/ would be rejected).
Allowing this would require lineage files attached to each release, that don't follow the scope of all future versions, it's more efficient to dump all patch files and metadata headers into a single, standard release tag.

If using the second option (distributing on a web server), the header files should be placed in the specified URL remote, alongside patch files specified in BANDAGE_PATCHES.
Bandage will literally append the header file names to the remote (i.e. the request URL for a BANDAGE_LINEAGE fetch, if the remote was https://example.com/patches/, would be https://example.com/patches/BANDAGE_LINEAGE).
This applies to patch names as well, if the patch name is not another URL.

If you want to point bandage.Supply to a Github repository's contents, use raw.githubusercontent.com (i.e. https://raw.githubusercontent.com/octocat/Spoon-Knife/). bandage.Supply will treat it like an ordinary web server.

Bandage API
===========

API
---
Details API structures under parent bandage.* and their usage.

Front-Facing
------------
.. autoclass:: bandage.Patcher
   :special-members: __init__

.. autoclass:: bandage.Weave
   :special-members: __init__

.. autoclass:: bandage.Supply
   :special-members: __init__

Exceptions
----------
.. autoclass:: bandage.Exceptions
   :members:

Backend
-------
**These aren't intended for usage.**

.. autoclass:: bandage.Backend
   :members:

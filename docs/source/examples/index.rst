.. _examples:

Examples
========

Each example is a complete pipeline you can run in a few minutes: an
install command, the configuration file, an input to test it on, and the
output to expect. The configuration files are in the ``examples/`` folder of
the `Juturna repository <https://github.com/meetecho/juturna>`_, and the
pages show them as they are.

.. list-table::
   :header-rows: 1
   :widths: 22 14 22 14 14 14

   * - Example
     - Extras
     - Download
     - Hardware
     - OS
     - Released
   * - :doc:`video_detection`
     - ``av``, ``onnx``
     - about 270 MB of packages, a 3.7 MB model, a 2 MB video
     - CPU
     - Linux (tested)
     - Not yet: the nodes ship with the next juturna-nodes release

The download is the size of a fresh virtual environment with the example
installed, plus the model and the test input fetched on the first run.

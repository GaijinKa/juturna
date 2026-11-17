.. _troubleshooting:

Troubleshooting
===============

The errors you are most likely to meet, what they mean and what to do.

A node type cannot be found
---------------------------

``ModuleNotFoundError`` from ``warmup()``, when the nodes are built, means Juturna could not
import the ``type`` of a node:

- ``node type AudioRtp comes with the juturna-nodes package, which is not
  installed``: a type without a prefix is an official node. Install it with
  ``pip install juturna-nodes``.
- A ``contrib.<package>.nodes.<Node>`` or ``extensions.nodes.<Node>`` type is
  imported as ``juturna.contrib...`` or ``juturna.extensions...``: the package
  that holds it must be installed, or its ``src`` folder must be on
  ``PYTHONPATH``, as in the :ref:`tutorial <tutorial>`.

Run ``python -m juturna validate --config pipeline.json`` before launching:
the "Node types and arguments" check finds these errors without starting
anything.

A stopped pipeline does not start again
---------------------------------------

``PipelineStoppedError`` on ``warmup()`` or ``start()``: a stopped pipeline
cannot be resumed. Call ``destroy()`` and create a new ``Pipeline`` from the
same configuration. The :doc:`lifecycle <explain/pipelines>` shows every legal
transition.

``PipelineBusyError`` means another lifecycle operation is still running on
the same pipeline, for example a ``start()`` called while ``stop()`` has not
returned. Wait for the first one to finish. ``kill()`` during a ``stop()`` is
allowed: it turns the stop into a kill.

A configuration cannot read an environment variable
---------------------------------------------------

``EnvVarNotAllowedError`` names the variable and the node that reads it with
``$JT_ENV_``. The pipeline was created with a list of allowed variables
(``serve`` builds it from ``--allow-env``) and this one is not in it. Add the
name, or a pattern such as ``MODEL_*``, to the list, or give the value
through an environment file. See :doc:`how_to/environment`.

The HTTP service answers 401
----------------------------

``serve`` requires a bearer token on every request. Without
``JUTURNA_SERVICE_TOKEN`` in its environment it generates one at startup and
prints it on the console, not in the logs. Send it as
``Authorization: Bearer <token>``. ``--no-auth`` turns the check off, for
local experiments only. See :doc:`how_to/serve_pipelines`.

A remote node drops part of its output
--------------------------------------

The remote service sends back only values it can encode, and drops the rest
with a warning. Started with ``remotize --strict``, it fails the request with
``DATA_LOSS`` instead. Make the node produce payloads and ``meta`` values of
types the service can carry, or accept the warning. The remote protocol of
3.0 does not talk to 2.x clients: upgrade both sides together. See
:doc:`how_to/remotise_node`.

Still stuck?
------------

Open an issue on `GitHub <https://github.com/meetecho/juturna/issues>`_ with
the configuration and the log, or
`ping the maintainers <https://www.meetecho.com/en/?utm_source=juturna-docs&utm_medium=docs&utm_campaign=juturna3>`_ at Meetecho.

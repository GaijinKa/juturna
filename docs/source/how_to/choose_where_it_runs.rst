.. _choose_where_it_runs:

Choose where it runs
====================

A pipeline runs in four places. In the first three, the configuration and
its nodes stay the same. A browser tab uses the same configuration format and
node model, but only the nodes and models that work on Pyodide, so a pipeline
written for a server may need other nodes there. Pick the place that fits,
then follow its guide.

One process
    ``python -m juturna launch --config pipeline.json``: every node in worker
    threads of the same process (the default ``threading`` transport).
    Guide: :doc:`create_pipelines`.

An HTTP service
    ``python -m juturna serve``, then send the same JSON to its REST API to
    create, start and stop pipelines. Needs the ``httpwrapper`` group.
    Guide: :doc:`serve_pipelines`.

A node on another machine
    ``python -m juturna remotize`` on the remote machine, and
    ``"warped": true`` with a ``warp_configuration`` on the node in the
    pipeline. Needs the ``warp`` group. Guide: :doc:`remotise_node`.

A browser tab
    ``"transport": "browser"`` in the pipeline, run by ``juturna-browser`` in
    the Web Workers of a page, on Pyodide. Guide: :doc:`run a pipeline in a page </browser/guide>`.

To ship any of them in a container, see :doc:`docker`. How the threads and
the browser backends differ underneath is in :doc:`/explain/transports`.

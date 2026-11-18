.. _choose_where_it_runs:

Choose where it runs
====================

The same pipeline configuration runs in four places, and its nodes do not
change from one to the other. Pick the one that fits, then follow its guide.

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
    the Web Workers of a page, on Pyodide. Guide: :doc:`/browser/guide`.

To ship any of them in a container, see :doc:`docker`. How the threads and
the browser backends differ underneath is in :doc:`/explain/transports`.

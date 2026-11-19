.. _work_with_meetecho:

Work with Meetecho
==================

Juturna is written and maintained by `Meetecho <https://www.meetecho.com/en/?utm_source=juturna-docs&utm_medium=docs&utm_campaign=juturna3>`_,
a spin-off of the University of Napoli Federico II that has built real-time
media systems since 2009, and the team behind the Janus® WebRTC server. When
a pipeline has to reach production, the people who wrote the library can
help.

Node development
----------------
Meetecho writes the nodes your pipeline is missing: a source for your
protocol or device, a model wrapped as a node, a sink towards your systems,
packaged and tested like the official ones.

Performance tuning
------------------
Meetecho measures where a pipeline spends its time and changes what makes
the difference: node placement, remote nodes on a GPU, worker layout,
transport.

Scaling
-------
Meetecho helps you move the heavy nodes of a pipeline off its machine: they
run as remote services, on a GPU or on other machines, shared by several
pipelines or, without sticky state, replicated behind a load balancer (see
:ref:`explain_remote`). It also sizes the hardware, and the limits of each
remote service, to the load you expect.

Consulting
----------
Meetecho helps you design the pipeline before it is written: which nodes,
where each one runs, and how it fits with the rest of your stack, including
Janus.

Support
-------
Meetecho supports the pipelines you run in production: answers from the
maintainers, fixes, and upgrades between Juturna versions. Vulnerabilities
follow the `security policy <https://github.com/meetecho/juturna/blob/main/SECURITY.md>`_, which says how to report them
privately and how Meetecho, as the open-source software steward of Juturna
under the EU Cyber Resilience Act, handles and discloses them.

A typical start is a call on Janus: its audio reaches a Juturna pipeline as
an RTP stream, and the results go back to your systems.

.. container:: jt-figure

   .. raw:: html
      :file: diagrams/janus_call.svg

   **Figure 1.** One call: Janus or Asterisk forwards the audio as RTP to ``AudioRtp``, AI nodes process it, ``NotifierHTTP`` posts the results.

.. button-link:: https://www.meetecho.com/en/?utm_source=juturna-docs&utm_medium=docs&utm_campaign=juturna3#contact
    :color: primary

    Talk to the Meetecho team

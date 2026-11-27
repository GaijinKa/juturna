.. _explain_messages:

Messages and payloads
=====================

Every byte that flows through a pipeline flows inside a ``Message``. A
message is an envelope, with versioning, timing and metadata, and its
payload is the data, of a declared type. Every message carries who made it
and when, so it can be read without any other context.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/message.svg

   **Figure 1.** The fields of a message. The whole message becomes read-only when it is transmitted.

Messages
--------

Besides ``creator``, ``version``, ``payload``, ``meta`` and ``timers``, a
message has a few methods:

``message.to_dict()`` and ``message.to_json(encoder)`` serialise it, for a
destination that needs text (nodes use them in ``dump_json()``).

``message.timeit(t_name)`` is a context manager that stores in ``timers``
how long the operations inside it took:

.. code-block:: python

  with message.timeit('inference_time'):
      annotated_image = model.infer(message.payload.image)

  message.timers
  # {'inference_time': <EXEC_TIME>}

Payloads
--------

All payload types inherit from ``BasePayload``, whose ``clone()`` makes a
deep copy. The built-in payloads:

- ``AudioPayload`` carries ``np.ndarray`` audio waveforms with metadata
  (sampling rate, channels, start/end timestamps).
- ``ImagePayload`` wraps multidimensional ``np.ndarray`` arrays containing
  images, attaching metadata such as width, height, depth, pixel format, and
  timestamp.
- ``VideoPayload`` holds a tuple of ``ImagePayload``, with metadata on frames
  per second and duration (start and end timestamps).
- ``BytesPayload`` only contains an array of bytes.
- ``Batch`` contains a tuple of messages, for nodes that collect several
  messages and transmit them together. The messages can be given as any
  sequence, and are frozen together with the message that carries the batch.
- ``ObjectPayload`` is a subclass of ``dict`` designed to hold arbitrary key-value
  pairs. Two of them are equal when their content is (arrays included), and an
  ``ObjectPayload`` is equal to a plain ``dict`` with the same content. Like a
  ``dict``, it cannot be hashed, so it cannot be a dictionary key or a set item.

``message.to_json()`` writes the payload with its ``serialize`` method. Arrays
become lists, bytes become base64 text and sets become lists, also when they
are values of an ``ObjectPayload`` or of the message ``meta``.

Immutability
------------

Messages and payloads are **immutable** once transmitted. This is what makes
transmission zero-copy: every destination gets the same object, and can be
sure no other node changed the data in it.

A payload never changes once created; only a ``Draft`` (below) can be filled
in until the message is transmitted. A new message can be changed, apart
from its payload, until a node transmits it:

.. code-block:: python

  from juturna.components import Message
  from juturna.payloads import AudioPayload


  message = Message(
    creator='creator_name',
    version=1,
    payload=AudioPayload()
  )

  # this is allowed
  message.version = 2

  # this will throw an error!
  message.payload.channels = 2

  Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<string>", line 4, in __setattr__
  dataclasses.FrozenInstanceError: cannot assign to field 'channels'

To fill a payload one field at a time, create the message with a ``Draft``
of the payload type: it behaves like that payload, but can be changed until
the message is transmitted.

.. code-block:: python

  from juturna.components import Message
  from juturna.payloads import Draft, AudioPayload


  message = Message(
    creator='creator_name',
    version=1,
    payload=Draft(AudioPayload)
  )

  # this is allowed now
  message.payload.channels = 2

Nodes make a message immutable (they `freeze` it) when they transmit it, so
there is nothing to call.

Changing a received message
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A message received in ``update()`` is frozen. To send it on with changes, ask
it for a copy:

.. code-block:: python

  def update(self, message: Message, **kwargs):
      to_send = message.copy(creator=self.name)

      to_send.meta['checked'] = True
      to_send.version += 1

      self.transmit(to_send)

``copy()`` returns a new message, with its own ``id`` and creation time, that
is not frozen. Version, meta and timers are copied, and meta can be changed
again at every level (a list that freezing turned into a tuple stays a tuple).
The payload is the same object, as payloads never change: to send different
data, assign a new payload, built with a ``Draft`` or from
``message.payload.clone()``.

The standard ``copy.copy()``, ``copy.deepcopy()`` and ``pickle`` work on
messages too, with a different meaning: they give the same message again,
with the same ``id``, and frozen if the original is.

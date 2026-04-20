"""
PassthroughWithFeedback

@ Author: Antonio Bevilacqua, Paolo Saviano
@ Email: abevilacqua@meetecho.com, psaviano@meetecho.com

Test node: return input messages and a feedback after a delay.
"""

import time

from juturna.components import Node
from juturna.components import Message

from juturna.payloads import BasePayload, Batch


class PassthroughWithFeedback(Node[BasePayload, BasePayload]):
    """Node implementation class"""

    def __init__(self, delay: int, **kwargs):
        """
        Parameters
        ----------
        delay : int
            Wait time before returning input messages to the output.
        kwargs : dict
            Supernode arguments.

        """
        super().__init__(**kwargs)

        self._delay = delay
        self._transmitted = 0

    def augument_message(self, message):
        """Augument the message with feedback from the same source"""
        feedbacks = self.pick_feedback(message.creator)
        self.logger.info(f'feedbacks: {feedbacks}')
        with_feedback = Message[Batch](
            creator=message.creator,
            version=message.version,
            payload=Batch(messages=(message, *feedbacks)),
            timers_from=message,
        )
        return with_feedback

    def update(self, message: Message[BasePayload]):
        """
        Receive a message from downstream, transmit a message upstream
        with the incoming payload plus the feedback from the same source,
        and stores the last message only
        """
        self.logger.info(f'received {len(message.payload.messages)} messages')

        self.logger.info(
            f'message {message.version} received from: {message.creator}'
        )

        for msg in message.payload.messages:
            self.logger.info(f'message payload: {msg.payload}')

        to_send = Message[Batch](
            creator=self.name,
            version=message.version,
            payload=message.payload,
            feedback=(message.payload.messages[0], message.creator),
            timers_from=message,
        )

        to_send.meta = dict(message.meta)

        self._transmitted += 1

        with to_send.timeit(f'{self.name}_delay'):
            time.sleep(self._delay)

        self.transmit(to_send)

    def next_batch(self, sources: dict) -> dict:
        """Synchronisation policy"""
        self.logger.info('using custom policy')
        self.logger.info(f'expected sources: {self.origins}')

        return {source: list(range(len(sources[source]))) for source in sources}

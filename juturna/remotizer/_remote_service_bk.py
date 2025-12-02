"""
gRPC Server endpoint that receives and deserializes MessageProtoEnvelope
Supports all payload types: Audio, Image, Video, Bytes, Object, Batch
"""

import grpc
import numpy as np
import logging
from concurrent import futures
from typing import Any
from collections.abc import Callable
from juturna.payloads import (
    AudioPayload,
    ImagePayload,
    VideoPayload,
    BytesPayload,
    ObjectPayload,
    Batch,
)
from juturna.components import Message

# Import generated protobuf code
from generated.payloads_pb2 import (
    MessageProtoEnvelope,
    MessageProto,
    AudioPayloadProto,
    ImagePayloadProto,
    VideoPayloadProto,
    BytesPayloadProto,
    ObjectPayloadProto,
    BatchProto,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# DESERIALIZATION UTILITIES (these would typically go into the payloads classes)
# ==============================================================================


def deserialize_audio_payload(payload: AudioPayloadProto) -> dict[str, Any]:
    """Deserialize AudioPayload to Python dict with numpy array"""
    audio_data = np.frombuffer(payload.audio_data, dtype=payload.dtype)
    audio_data = audio_data.reshape(payload.shape)

    return {
        'audio': audio_data,
        'sampling_rate': payload.sampling_rate,
        'channels': payload.channels,
        'start': payload.start,
        'end': payload.end,
        'dtype': payload.dtype,
        'shape': list(payload.shape),
    }


def deserialize_image_payload(payload: ImagePayloadProto) -> dict[str, Any]:
    """Deserialize ImagePayload to Python dict with numpy array"""
    image_data = np.frombuffer(payload.image_data, dtype=payload.dtype)

    if payload.depth == 1:
        shape = (payload.height, payload.width)
    else:
        shape = (payload.height, payload.width, payload.depth)

    image_data = image_data.reshape(shape)

    return {
        'image': image_data,
        'width': payload.width,
        'height': payload.height,
        'depth': payload.depth,
        'pixel_format': payload.pixel_format,
        'timestamp': payload.timestamp,
        'dtype': payload.dtype,
    }


def deserialize_video_payload(payload: VideoPayloadProto) -> dict[str, Any]:
    """Deserialize VideoPayload to Python dict with list of numpy arrays"""
    frames = [deserialize_image_payload(frame) for frame in payload.frames]

    return {
        'frames': frames,
        'frames_per_second': payload.frames_per_second,
        'start': payload.start,
        'end': payload.end,
        'codec': payload.codec,
        'duration': payload.duration,
        'num_frames': len(frames),
    }


def deserialize_bytes_payload(payload: BytesPayloadProto) -> dict[str, Any]:
    """Deserialize BytesPayload to Python dict"""
    return {
        'content': payload.content,
        'content_type': payload.content_type,
        'filename': payload.filename,
        'size': len(payload.content),
    }


def deserialize_object_payload(payload: ObjectPayloadProto) -> dict[str, Any]:
    """Deserialize ObjectPayload (Struct) to Python dict"""
    from google.protobuf.json_format import MessageTodict

    return MessageTodict(payload.data)


def deserialize_batch(payload: BatchProto) -> dict[str, Any]:
    """Deserialize Batch to Python dict"""
    messages = [deserialize_message(msg) for msg in payload.messages]

    return {
        'messages': messages,
        'metadata': dict(payload.metadata),
        'created_at': payload.created_at,
        'batch_id': payload.batch_id,
        'total_size': payload.total_size,
        'num_messages': len(messages),
    }


def deserialize_message(message: MessageProto) -> dict[str, Any]:
    """Deserialize Message to Python dict"""
    # Extract basic message info
    result = {
        'created_at': message.created_at,
        'creator': message.creator,
        'version': message.version,
        'meta': dict(message.meta),
        'timers': dict(message.timers),
        'payload': None,
        'payload_type': None,
    }

    # Deserialize payload based on type
    if message.payload.Is(AudioPayloadProto.DESCRIPTOR):
        audio = AudioPayloadProto()
        message.payload.Unpack(audio)
        result['payload'] = deserialize_audio_payload(audio)
        result['payload_type'] = 'AudioPayload'

    elif message.payload.Is(ImagePayloadProto.DESCRIPTOR):
        image = ImagePayloadProto()
        message.payload.Unpack(image)
        result['payload'] = deserialize_image_payload(image)
        result['payload_type'] = 'ImagePayload'

    elif message.payload.Is(VideoPayloadProto.DESCRIPTOR):
        video = VideoPayloadProto()
        message.payload.Unpack(video)
        result['payload'] = deserialize_video_payload(video)
        result['payload_type'] = 'VideoPayload'

    elif message.payload.Is(BytesPayloadProto.DESCRIPTOR):
        bytes_payload = BytesPayloadProto()
        message.payload.Unpack(bytes_payload)
        result['payload'] = deserialize_bytes_payload(bytes_payload)
        result['payload_type'] = 'BytesPayload'

    elif message.payload.Is(ObjectPayloadProto.DESCRIPTOR):
        obj = ObjectPayloadProto()
        message.payload.Unpack(obj)
        result['payload'] = deserialize_object_payload(obj)
        result['payload_type'] = 'ObjectPayload'

    elif message.payload.Is(BatchProto.DESCRIPTOR):
        batch = BatchProto()
        message.payload.Unpack(batch)
        result['payload'] = deserialize_batch(batch)
        result['payload_type'] = 'Batch'

    return result


def deserialize_envelope(envelope: MessageProtoEnvelope) -> dict[str, Any]:
    """Deserialize complete MessageProtoEnvelope to Python dict"""
    return {
        'id': envelope.id,
        'sender': envelope.sender,
        'receiver': envelope.receiver,
        'correlation_id': envelope.correlation_id,
        'response_to': envelope.response_to,
        'ttl': envelope.ttl,
        'created_at': envelope.created_at,
        'configuration': dict(envelope.configuration),
        'metadata': dict(envelope.metadata),
        'priority': envelope.priority,
        'message_type': envelope.message_type,
        'message': deserialize_message(envelope.message),
    }


# ============================================================================
# MESSAGE HANDLER REGISTRY
# ============================================================================


class MessageHandler:
    """Registry for handling different message types"""

    def __init__(self):
        self.handlers: dict[str, Callable] = {}

    def register(self, payload_type: str, handler: Callable):
        """Register a handler for a specific payload type"""
        self.handlers[payload_type] = handler
        logger.info(f'Registered handler for {payload_type}')

    def handle(self, envelope_dict: dict[str, Any]) -> Any:
        """Route message to appropriate handler"""
        payload_type = envelope_dict['message']['payload_type']

        if payload_type not in self.handlers:
            logger.warning(f'No handler registered for {payload_type}')
            return None

        handler = self.handlers[payload_type]
        return handler(envelope_dict)


# ============================================================================
# gRPC SERVICE IMPLEMENTATION
# ============================================================================

from generated import messaging_service_pb2
from generated import messaging_service_pb2_grpc


class MessagingServiceImpl(messaging_service_pb2_grpc.MessagingServiceServicer):
    """Implementation of the gRPC Messaging Service"""

    def __init__(self):
        self.handler = MessageHandler()

    def SendMessage(self, request: MessageProtoEnvelope, context):
        """Handle incoming message and return acknowledgment"""
        import time

        try:
            # Log incoming message
            logger.info(f'Received envelope {request.id} from {request.sender}')

            # Deserialize the envelope
            envelope_dict = deserialize_envelope(request)

            # Log details
            logger.info(
                f'Message type: {envelope_dict["message"]["payload_type"]}'
            )
            logger.info(f'Creator: {envelope_dict["message"]["creator"]}')

            # Handle the message
            result = self.handler.handle(envelope_dict)

            # Create response
            response = MessageProtoEnvelope()
            response.id = f'ack-{request.id}'
            response.success = True
            response.message = f'Message processed successfully: {result}'
            response.envelope_id = request.id
            response.processed_at = time.time()

            return response

        except Exception as e:
            logger.error(f'Error processing message: {e}', exc_info=True)

            response = messaging_service_pb2.MessageResponse()
            response.success = False
            response.message = f'Error: {str(e)}'
            response.envelope_id = request.id
            response.processed_at = time.time()

            return response

    def SendAndReceive(self, request: MessageProtoEnvelope, context):
        """Handle request-response pattern"""
        # Process the incoming message
        self.SendMessage(request, context)

        # Create response envelope
        response_envelope = MessageProtoEnvelope()
        response_envelope.id = f'resp-{request.id}'
        response_envelope.sender = request.receiver
        response_envelope.receiver = request.sender
        response_envelope.correlation_id = request.correlation_id
        response_envelope.response_to = request.id

        # Create response message with result
        # (simplified - in production you'd build a proper response)
        import time

        response_envelope.message.created_at = time.time()
        response_envelope.message.creator = 'response_handler'
        response_envelope.message.version = 1

        return response_envelope

    def StreamMessages(self, request_iterator, context):
        """Handle streaming messages"""
        for envelope in request_iterator:
            response = self.SendMessage(envelope, context)
            yield response


# ============================================================================
# SERVER STARTUP
# ============================================================================


def serve(port: int = 50051, max_workers: int = 10):
    """Start the gRPC server"""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.max_send_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
        ],
    )

    # Add the service
    messaging_service_pb2_grpc.add_MessagingServiceServicer_to_server(
        MessagingServiceImpl(), server
    )

    # Bind to port
    server.add_insecure_port(f'[::]:{port}')

    logger.info(f'Starting gRPC server on port {port}')
    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info('Shutting down server...')
        server.stop(0)


if __name__ == '__main__':
    serve()

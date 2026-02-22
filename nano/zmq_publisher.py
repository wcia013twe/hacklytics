import zmq
import json
import time


class ZmqPublisher:
    """
    ZeroMQ PUB socket wrapper for the Jetson side.

    The Jetson connects to the backend (which binds). This means the backend
    is the stable endpoint — the Jetson can reconnect transparently on WiFi
    drops without any extra logic.

    Usage:
        pub = ZmqPublisher("192.168.1.10")
        pub.publish({"hazard_level": "CLEAR", ...})
        pub.close()
    """

    PORT = 5555

    def __init__(self, backend_ip: str, device_id: str = "jetson_alpha_01"):
        self.device_id = device_id
        self.session_id = f"mission_{time.strftime('%Y_%m_%d_%H%M%S')}"

        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.PUB)

        # Drop oldest messages if the send buffer fills up (keeps camera loop unblocked)
        self._sock.setsockopt(zmq.SNDHWM, 100)

        endpoint = f"tcp://{backend_ip}:{self.PORT}"
        self._sock.connect(endpoint)
        print(f"[ZMQ] Publisher connected → {endpoint}  (session: {self.session_id})")

    def publish(self, packet: dict) -> None:
        """
        Stamps device_id / session_id onto the packet and sends it.
        Non-blocking — drops silently if HWM is reached.
        """
        packet["device_id"] = self.device_id
        packet["session_id"] = self.session_id

        try:
            self._sock.send_string(json.dumps(packet), zmq.NOBLOCK)
        except zmq.Again:
            pass  # HWM reached — drop rather than block the camera loop

    def close(self) -> None:
        self._sock.close()
        self._ctx.term()

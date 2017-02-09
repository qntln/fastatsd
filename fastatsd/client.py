from typing import Tuple, Any, Iterable
import functools
import socket
import time
import threading
import random
import atexit
import warnings

import cystatsd



class Timer:
	'''
	A context manager/decorator for statsd.timing(). This is based on code from the statsd package.
	'''

	def __init__(self, client: 'FastatsClient', stat: str, rate: float = 1) -> None:
		self.client = client
		self.stat = stat
		self.rate = rate
		self.ms = None  # type: int
		self._sent = False
		self._start_time = None  # type: float


	def __call__(self, f):
		@functools.wraps(f)
		def wrapper(*args, **kw):
			with self:
				return f(*args, **kw)
		return wrapper


	def __enter__(self) -> 'Timer':
		return self.start()


	def __exit__(self, *args: Any) -> None:
		self.stop()


	def start(self) -> 'Timer':
		self.ms = None
		self._sent = False
		self._start_time = time.monotonic()
		return self


	def stop(self, send: bool = True) -> 'Timer':
		if self._start_time is None:
			raise RuntimeError('Timer has not started.')
		dt = time.monotonic() - self._start_time
		self.ms = int(round(1000 * dt))  # Convert to milliseconds.
		if send:
			self.send()
		return self


	def send(self) -> None:
		if self.ms is None:
			raise RuntimeError('No data recorded.')
		if self._sent:
			raise RuntimeError('Already sent data.')
		self._sent = True
		self.client.timing(self.stat, self.ms, self.rate)



class CystatsSender(threading.Thread):
	'''
	Thread sending the queue to statsd server.
	'''

	def __init__(self, queue: cystatsd.MetricCollector, cv: threading.Condition, server_addr: Tuple[str, int]) -> None:
		super().__init__(daemon = True)
		self._queue = queue
		self._cv = cv
		self._running = False  # Should be accessed only locked with cv
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self._server_addr = server_addr


	def _flush(self, buffer: Iterable[bytes]) -> None:
		'''
		Send several UDP datagrams with contents from the ``buffer`` iterable.
		'''
		for data in buffer:
			try:
				self._sock.sendto(data, self._server_addr)
			except socket.error:
				pass


	def run(self) -> None:
		'''
		Thread loop sending the serialized data to server.
		'''
		buffer = []  # type: Iterable[bytes]
		while True:
			# We don't use context managers as it is significantly slower than acquire-release access
			try:
				# --- Critical section beginning ---
				self._cv.acquire()
				# Query _running inside the locked section
				if not self._running:
					break
				# Wakeup of the cv doesn't always mean there is new data.
				self._cv.wait()
				# Get the data to be sent. This returns a generator with data to be sent in individual UDP datagrams.
				buffer = self._queue.flush()
				# _running has to be checked twice because the notify call can come before wait,
				# which would lead to a deadlock.
				if not self._running:
					break
				# --- Critical section end ---
			finally:
				self._cv.release()
			self._flush(buffer)
		# Flush the data at exit
		self._flush(buffer)


	def ask_stop(self) -> None:
		'''
		Ask the thread to send queued messages and stop.
		'''
		assert self._running
		try:
			self._cv.acquire()
			self._running = False
			self._cv.notify()
		finally:
			self._cv.release()


	def start(self):
		'''
		Start the sender thread.
		'''
		try:
			self._cv.acquire()
			self._running = True
		finally:
			self._cv.release()
		super().start()



class FastatsClient:
	'''
	Fast Statsd client.
	'''
	_sentinel = object()


	def __init__(self, host: str = 'localhost', port: int = 8125, prefix: str = '', maxudpsize: Any = _sentinel) -> None:
		'''
		Create a new client.

		:param host: Host of the statsd server.
		:param port: Port of the statsd server, 8125 by default.
		:param prefix: String that will be prefixed to any stat description.
		:param maxudpsize: Ignored in this implementation.
		'''
		self._prefix = prefix + '.' if prefix else ''
		self._server_addr = (socket.gethostbyname(host), port)
		self._queue = cystatsd.MetricCollector()
		self._queue_cv = threading.Condition()
		if maxudpsize is not self._sentinel:
			warnings.warn('Fastatsd client doesn\'t support maxudpsize')
		self._start_sender_thread()


	def pipeline(self):
		raise NotImplementedError()


	def timer(self, stat: str, rate: float = 1) -> Timer:
		'''
		Return a context manager object which will send ``timing`` information about its duration when it exits.
		'''
		return Timer(self, stat, rate)


	def timing(self, stat: str, delta: float, rate: float = 1) -> None:
		'''
		Send new timing measurement. ``delta`` is in milliseconds.
		'''
		if random.random() > rate:
			return
		try:
			self._queue_cv.acquire()
			self._queue.push_timer(self._prefix + stat, delta, rate)
			self._queue_cv.notify()
		finally:
			self._queue_cv.release()


	def incr(self, stat: str, count: int = 1, rate: float = 1) -> None:
		'''
		Increment a stat by ``count``.
		'''
		if random.random() > rate:
			return
		try:
			self._queue_cv.acquire()
			self._queue.push_counter(self._prefix + stat, count, rate)
			self._queue_cv.notify()
		finally:
			self._queue_cv.release()


	def decr(self, stat: str, count: int = 1, rate: float = 1) -> None:
		'''
		Decrement a stat by ``count``.
		'''
		self.incr(stat, -count, rate)


	def gauge(self, stat: str, value: int, rate: float = 1, delta: bool = False) -> None:
		'''
		Set a gauge value. If `delta` is True, the ``value`` is relative to the previous one.
		'''
		if random.random() > rate:
			return
		try:
			self._queue_cv.acquire()
			if value < 0 and not delta:
				# If we want to set gauge value to absolute -x, we have to reset it to 0 and then decrement by x, as
				# -x is perceived as relative change!
				self._queue.push_gauge(self._prefix + stat, 0, 1)
			self._queue.push_gauge(self._prefix + stat, value, rate, delta)
			self._queue_cv.notify()
		finally:
			self._queue_cv.release()


	def set(self, stat: str, value: int, rate: float = 1) -> None:
		'''
		Increment a set value.
		'''
		if random.random() > rate:
			return
		try:
			self._queue_cv.acquire()
			self._queue.push_set(self._prefix + stat, value, rate)
			self._queue_cv.notify()
		finally:
			self._queue_cv.release()


	def _start_sender_thread(self):
		self._sender_thread = CystatsSender(self._queue, self._queue_cv, self._server_addr)
		self._sender_thread.start()
		atexit.register(self.stop)


	def stop(self) -> None:
		'''
		Flush queued data and stop the client.
		'''
		self._sender_thread.ask_stop()
		self._sender_thread.join()
		# Calling stop() at exit is not needed anymore. Calling unregister will allow the interpreter to free this
		# instance and its memory.
		atexit.unregister(self.stop)


	def __enter__(self) -> 'FastatsClient':
		if not self._sender_thread.is_alive():
			self._start_sender_thread()
		return self


	def __exit__(self, *args) -> None:
		self.stop()

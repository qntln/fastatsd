from typing import Tuple

from fastatsd.client import FastatsClient
from unittest import mock
import time
import pytest
import re



class FakeSocket:
	def __init__(self):
		self.sent = []

	def sendto(self, data, addr):
		self.sent.append(data)



@pytest.fixture(scope = 'function')
def mock_socket(monkeypatch):
	fake_socket = FakeSocket()
	mock_obj = mock.MagicMock()
	mock_obj.side_effect = 10 * [fake_socket]
	monkeypatch.setattr('fastatsd.client.socket.socket', mock_obj)
	return fake_socket


def _decompose_message(message: bytes) -> Tuple[str, float, str]:
	message_str = str(message)[2:-1]
	stat, delay, unit = re.split(':|\||@', message_str)
	return stat, float(delay), unit


def test_timer_no_rate(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		with statsd.timer('test'):
			time.sleep(0.1)

	stat, delay, unit = _decompose_message(mock_socket.sent[0])
	assert stat == 'testing.test'
	assert 50 < delay < 150
	assert unit == 'ms'


def test_incr(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.incr('test', 123)

	assert mock_socket.sent == [b'testing.test:123|c']


def test_incr_without_prefix(mock_socket):
	with FastatsClient() as statsd:
		statsd.incr('test', 123)

	assert mock_socket.sent == [b'test:123|c']


def test_incr_rate(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		for i in range(10000):
			statsd.incr('someALittleBitLongDescribtionOfTheMetric', 123, 0.5)

	approx_messages_count = 0
	messages_length = 0
	for buffer in mock_socket.sent:
		approx_messages_count += buffer.count(b':')
		messages_length += len(buffer)

	# Uncomment these for debugging output
	# print('Packet number', len(mock_socket.sent))
	# print('Approx packet length', messages_length/len(mock_socket.sent))
	# print('Rate limited msgs count', approx_messages_count)

	assert mock_socket.sent[0].startswith(b'testing.someALittleBitLongDescribtionOfTheMetric:123|c|@0.5')
	assert 1000 < approx_messages_count < 9000, 'Rate 10000 calls at rate 0.5 should produce about 5000 statsd calls'


def test_context_mgr_reuse(mock_socket):
	statsd_reusable = FastatsClient(prefix = 'testing')
	with statsd_reusable as statsd:
		statsd.incr('test', 123)
	with statsd_reusable as statsd:
		statsd.incr('test2', 234)

	assert mock_socket.sent == [b'testing.test:123|c', b'testing.test2:234|c'] or mock_socket.sent == [b'testing.test:123|c\ntesting.test2:234|c']


def test_no_context_mgr(mock_socket):
	statsd = FastatsClient(prefix = 'testing')
	statsd.incr('test', 123)
	statsd.stop()

	assert mock_socket.sent == [b'testing.test:123|c']


def test_decr(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.decr('test', 123)

	assert mock_socket.sent == [b'testing.test:-123|c']


def test_gauge(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.gauge('test', 123)

	assert mock_socket.sent == [b'testing.test:123.000000|g']


def test_gauge_negative(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.gauge('test', -123)

	assert mock_socket.sent == [b'testing.test:0.000000|g\ntesting.test:-123.000000|g']


def test_gauge_delta(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.gauge('test', 123, delta = True)

	assert mock_socket.sent == [b'testing.test:+123.000000|g']


def test_gauge_delta_negative(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.gauge('test', -123, delta = True)

	assert mock_socket.sent == [b'testing.test:-123.000000|g']


def test_set(mock_socket):
	with FastatsClient(prefix = 'testing') as statsd:
		statsd.set('test', 123)

	assert mock_socket.sent == [b'testing.test:123|s']

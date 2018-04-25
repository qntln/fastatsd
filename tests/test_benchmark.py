import pytest
from fastatsd.client import FastatsClient

statsd = pytest.importorskip('statsd')


def _incr_test(client):
	for i in range(10000):
		client.incr('someALittleBitLongDescriptionOfTheMetric', 123)


def _timer_test(client):
	for i in range(10000):
		with client.timer('someALittleBitLongDescriptionOfTheMetric'):
			pass


def test_fastatsd_incr_10000x(benchmark):
	with FastatsClient() as client:
		benchmark(_incr_test, client)


def test_fastatsd_timer_10000x(benchmark):
	with FastatsClient() as client:
		benchmark(_timer_test, client)


def test_statsd_incr_10000x(benchmark):
	client = statsd.StatsClient()
	benchmark(_incr_test, client)


def test_statsd_timer_10000x(benchmark):
	client = statsd.StatsClient()
	benchmark(_timer_test, client)

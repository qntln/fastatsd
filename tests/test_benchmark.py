from statsd import StatsClient

from fastatsd.client import FastatsClient


def _incr_test(statsd):
	for i in range(10000):
		statsd.incr('someALittleBitLongDescriptionOfTheMetric', 123)


def _timer_test(statsd):
	for i in range(10000):
		with statsd.timer('someALittleBitLongDescriptionOfTheMetric'):
			pass


def test_fastatsd_incr_10000x(benchmark):
	with FastatsClient() as statsd:
		benchmark(_incr_test, statsd)


def test_fastatsd_timer_10000x(benchmark):
	with FastatsClient() as statsd:
		benchmark(_timer_test, statsd)


def test_statsd_incr_10000x(benchmark):
	statsd = StatsClient()
	benchmark(_incr_test, statsd)


def test_statsd_timer_10000x(benchmark):
	statsd = StatsClient()
	benchmark(_timer_test, statsd)

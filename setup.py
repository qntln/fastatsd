import os
from distutils.core import setup



def read(relpath: str) -> str:
	with open(os.path.join(os.path.dirname(__file__), relpath)) as f:
		return f.read()


setup(
	name = 'fastatsd',
	version = read('version.txt').strip(),
	description = 'Fast StatsD client. Serves as a drop-in replacement for the statsd package.',
	long_description = read('README.rst'),
	author = 'Quantlane',
	author_email = 'code@quantlane.com',
	url = 'https://github.com/qntln/fastatsd',
	license = 'Apache 2.0',
	install_requires = [
		'ql-cystatsd==1.1.0',
	],
	packages = [
		'fastatsd',
	],
	classifiers = [
		'Development Status :: 4 - Beta',
		'License :: OSI Approved :: Apache Software License',
		'Natural Language :: English',
		'Programming Language :: Python :: 3 :: Only',
		'Programming Language :: Python :: 3.5',
	]
)

from setuptools import setup
import codecs
import re
import os

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    return codecs.open(os.path.join(here, *parts), 'r').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

setup(name='resultsdb',
      version=find_version('resultsdb', '__init__.py'),
      description='Results store for the Taskbot',
      author='Josef Skladanka',
      author_email='jskladan@redhat.com',
      license='GPLv2+',
      packages=['resultsdb', 'resultsdb.controllers', 'resultsdb.lib', 'resultsdb.models',
                'resultsdb.serializers'],
      package_dir={'resultsdb': 'resultsdb'},
      entry_points={
          'console_scripts': ['resultsdb=resultsdb.cli:main'],
          'resultsdb.messaging.plugins': [
              'dummy=resultsdb.messaging:DummyPlugin',
              'fedmsg=resultsdb.messaging:FedmsgPlugin',
              'stomp=resultsdb.messaging:StompPlugin',
          ],
      },
      include_package_data=True,
      )

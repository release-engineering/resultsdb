from setuptools import setup

setup(name='resultsdb',
      version='1.0.0',
      description='Results store for the Taskbot',
      author='Josef Skladanka',
      author_email='jskladan@redhat.com',
      license='GPLv2+',
      packages=['resultsdb', 'resultsdb.controllers', 'resultsdb.models', 'resultsdb.serializers'],
      package_dir={'resultsdb':'resultsdb'},
      entry_points=dict(console_scripts=['resultsdb=resultsdb.cli:main']),
      include_package_data=True,
     )

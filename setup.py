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
      install_requires = [
        'Flask>=0.9',
        'Flask-SQLAlchemy>=0.16',
        'SQLAlchemy>= 0.7',
        'MySQL-python >= 1.2.0',
        'WTForms>1.0',
        'Flask-WTF==0.8',
        'Flask-Login>=0.2.2',
        'Flask-RESTful >= 0.2.5',
        'six', # although this is a Flask-Restful dependency, it was not installed, adding manualy
        'iso8601 >= 0.1.4',
     ]
     )

#FIXME: Flask-WTF > 0.8 introduced API change for imports

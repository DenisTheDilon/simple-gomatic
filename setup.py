from setuptools import setup, find_packages

setup(name='simple-gomatic',
      version='0.1.0',
      description='API for configuring GoCD based in Gomatic',
      url='https://github.com/DenisTheDilon/simple-gomatic',
      author='Denis Odilon',
      author_email='dodilon@outlook.com',
      license='MIT',
      packages=find_packages(exclude=("tests",)),
      install_requires=[
          'requests'
      ],
      zip_safe=False)

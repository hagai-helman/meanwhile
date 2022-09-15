from setuptools import setup

setup(
    name='meanwhile',
    version='1.1.1',
    author='Hagai Helman Tov',
    author_email='hagai.helman@gmail.com',
    description='Very easy multithreading',
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url='https://github.com/hagai-helman/meanwhile',
    keywords=['threading', 'threads', 'multithreading'],
    py_modules=['meanwhile'],
    license='MIT',
    install_requires=[],
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        ],
)

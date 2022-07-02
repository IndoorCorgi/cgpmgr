from setuptools import setup

setup(
    name='cgpmgr',
    version='1.2',
    description='Controller tool of Raspberry Pi power management board "RPZ-PowerMGR".',
    author='Indoor Corgi',
    author_email='indoorcorgi@gmail.com',
    url='https://github.com/IndoorCorgi/cgpmgr',
    license='Apache License 2.0',
    packages=['cgpmgr'],
    install_requires=['docopt', 'RPi.GPIO'],
    entry_points={'console_scripts': ['cgpmgr=cgpmgr:cli',]},
    python_requires='>=3.6',
)

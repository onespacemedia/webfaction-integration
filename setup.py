from distutils.core import setup

setup(
    name = "webfaction-integration",
    version = '0.1',
    license = "BSD",
    description = "Deployment script for pushing local sites up to Webfaction servers.",
    author = "Daniel Samuels",
    author_email = "daniel.samuels1@gmail.com",
    url = "https://github.com/onespacemedia/webfaction-integration",
    packages = [
        "webfaction_integration",
    ],
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Framework :: Django",
    ],
)

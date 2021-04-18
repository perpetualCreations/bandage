"""
bandage, v1.0
Made by perpetualCreations

setup.py, packaging script for setuptools
"""

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt") as rh:
    requirements = rh.read().split("\n")

setuptools.setup(
    name="bandage",
    version="1.1",
    author="perpetualCreations",
    author_email="tchen0584@gmail.com",
    description="Patching library.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/perpetualCreations/bandage/",
    install_requires=requirements,
    packages=setuptools.find_packages(),
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)

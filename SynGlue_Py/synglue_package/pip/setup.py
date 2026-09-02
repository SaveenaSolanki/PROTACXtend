from setuptools import setup, find_packages
import os

def readme():
    with open(os.path.join(os.path.dirname(__file__), "README.md"), encoding="utf-8") as f:
        return f.read()

setup(
    name="synglue",
    version="0.1.4",
    description="Python client for SynGlue",
    long_description=readme(),
    long_description_content_type="text/markdown",
    author="Saveena Solanki",
    author_email="saveenas@iiitd.ac.in",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=["requests"],
)

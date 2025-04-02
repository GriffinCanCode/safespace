from setuptools import setup, find_packages

# This setup.py file is for compatibility with older versions of pip
# For modern installations, pyproject.toml will be used instead

setup(
    name="safespace",
    version="0.1.0",
    description="Safe Environment Creator and Manager",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="SafeSpace Team",
    author_email="info@safespace.example.com",
    url="https://github.com/username/safespace",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "psutil>=5.9.0",
        "click>=8.0.0",
        "pathlib>=1.0.1",
    ],
    extras_require={
        "network": ["pyroute2>=0.7.0"],
        "vm": ["qemu.py>=0.1.0"],
        "test": ["pytest>=7.0.0", "pytest-cov>=4.0.0"],
        "dev": [
            "black>=23.3.0",
            "isort>=5.12.0",
            "mypy>=1.2.0",
            "build>=0.10.0",
            "twine>=4.0.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "safespace=safespace.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Testing",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
)

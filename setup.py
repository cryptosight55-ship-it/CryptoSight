"""
Setup script for CryptoSight v2.0 - AI Crypto Trading Bot
"""

from setuptools import setup, find_packages
import os

# Read requirements
def read_requirements():
    req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(req_file, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read README
def read_readme():
    readme_file = os.path.join(os.path.dirname(__file__), 'README.md')
    try:
        with open(readme_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "CryptoSight v2.0 - AI Crypto Trading Bot"

setup(
    name="cryptosight",
    version="2.0.0",
    description="Professional-grade AI cryptocurrency trading bot",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="CryptoSight Team",
    author_email="team@cryptosight.ai",
    url="https://github.com/samannazir55/ai-crypto-trading-bot",
    packages=find_packages(),
    include_package_data=True,
    install_requires=read_requirements(),
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="cryptocurrency trading bot ai machine-learning binance",
    entry_points={
        'console_scripts': [
            'cryptosight=cli.main:main',
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/samannazir55/ai-crypto-trading-bot/issues",
        "Source": "https://github.com/samannazir55/ai-crypto-trading-bot",
        "Documentation": "https://github.com/samannazir55/ai-crypto-trading-bot/blob/main/README.md",
    },
)
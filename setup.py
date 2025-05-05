from setuptools import setup, find_packages

setup(
    name="option_levels_api",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi",
        "uvicorn",
        "pandas",
        "numpy",
        "yfinance",
        "python-dateutil",
        "scipy",
        "boto3",
        "mangum",
    ],
)
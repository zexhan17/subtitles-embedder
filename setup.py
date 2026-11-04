from setuptools import setup, find_packages

setup(
    name="subembed",
    version="1.0.0",
    description="Lossless Container Subtitle Embedder",
    author="User",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "subembed=subembed.cli:main",
            "subembed-gui=subembed.gui:launch_gui",
        ],
    },
    python_requires=">=3.8",
)

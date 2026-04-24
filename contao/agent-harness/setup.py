from setuptools import setup, find_namespace_packages

setup(
    name="contao-ai-cli",
    version="1.0.0",
    description="Agent-native CLI for Contao 5 CMS via SSH",
    author="web.werk.wien",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.contao": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0",
        "prompt_toolkit>=3.0",
    ],
    entry_points={
        "console_scripts": [
            "contao-ai-cli=cli_anything.contao.contao_cli:cli",
        ],
    },
    python_requires=">=3.10",
)

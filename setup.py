from setuptools import setup, find_packages

setup(
    name="contao-ai-cli",
    version="0.8.5",
    description="Agent-native CLI for Contao 5 CMS via SSH",
    author="web.werk.wien",
    license="MIT",
    url="https://github.com/webwerkwien/contao-ai-cli",
    packages=find_packages(include=["contao_ai_cli", "contao_ai_cli.*"]),
    package_data={
        "contao_ai_cli": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0",
        "prompt_toolkit>=3.0",
    ],
    entry_points={
        "console_scripts": [
            "contao-ai-cli=contao_ai_cli.contao_cli:cli",
        ],
    },
    python_requires=">=3.10",
)

from pathlib import Path
import shutil

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py

HERE = Path(__file__).resolve().parent


class BuildWithGuide(build_py):
    """Copy GUIDE.md from the repository root into the package.

    The guide sits at the root next to README, and package_data cannot reach
    outside the package directory. Without this copy an installed CLI carries no
    guide at all (`contao-ai-cli guide`, v0.26.0). AGENTS.md, the development
    guide, stays in the repository.
    """

    def _guide_target(self) -> str:
        return str(Path(self.build_lib) / "contao_ai_cli" / "GUIDE.md")

    def run(self):
        super().run()
        source = HERE / "GUIDE.md"
        if not source.is_file():
            # Fail the build rather than ship a package whose `guide` cannot work.
            raise FileNotFoundError(f"{source} is missing; the guide ships in the package since v0.26.0")
        target = Path(self._guide_target())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    # A strict PEP 660 editable install builds its link tree from these two, so the
    # copy has to be named here as well as written in run().
    def get_outputs(self, include_bytecode=True):
        return [*super().get_outputs(include_bytecode), self._guide_target()]

    def get_output_mapping(self):
        mapping = dict(super().get_output_mapping())
        mapping[self._guide_target()] = str(HERE / "GUIDE.md")
        return mapping


setup(
    name="contao-ai-cli",
    version="1.14.1",
    description="Agent-native CLI for Contao 5 CMS via SSH",
    author="web.werk.wien",
    license="MIT",
    url="https://github.com/webwerkwien/contao-ai-cli",
    # The test suite stays in the repository; an installed CLI has no use for it.
    packages=find_packages(include=["contao_ai_cli", "contao_ai_cli.*"],
                           exclude=["contao_ai_cli.tests", "contao_ai_cli.tests.*"]),
    package_data={
        "contao_ai_cli": ["skills/*.md"],
    },
    cmdclass={"build_py": BuildWithGuide},
    install_requires=[
        "click>=8.0",
        "prompt_toolkit>=3.0",
    ],
    entry_points={
        "console_scripts": [
            "contao-ai-cli=contao_ai_cli.contao_cli:main",
        ],
    },
    python_requires=">=3.10",
)

"""
Patrol 系统的 setup.py 配置

使用方法：
  pip install -e .

这会创建 'patrol' 命令行工具，可以直接使用：
  patrol --config wechat_patrol
  patrol --list-examples
"""

from setuptools import setup, find_packages

setup(
    name="open-autoglm-patrol",
    version="0.2.0",
    description="App Inspection System for Open-AutoGLM",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    author="Open-AutoGLM Contributors",
    packages=find_packages(),
    install_requires=[
        "Pillow>=12.0.0",
        "openai>=2.9.0",
        "PyYAML>=6.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "patrol=patrol.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)

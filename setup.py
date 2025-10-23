from __future__ import annotations

from setuptools import find_packages, setup

setup(
	name="farmlink",
	version="0.0.1",
	description="Digital coffee management platform",
	author="vulerotech",
	author_email="mezmure.dawit@vulero.et",
	packages=find_packages(include=["farmlink", "farmlink.*", "frappe_backend", "frappe_backend.*"]),
	include_package_data=True,
	python_requires=">=3.10",
)

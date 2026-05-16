from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def test_requirements_include_fastapi_email_validation_runtime_dependencies():
    requirements = read_project_file("requirements.txt")

    assert "email-validator==2.3.0" in requirements
    assert "dnspython==2.8.0" in requirements


def test_windows_build_copies_email_validator_metadata_into_pyinstaller_bundle():
    build_script = read_project_file("scripts/build.bat")

    assert "--hidden-import email_validator" in build_script
    assert "--copy-metadata email-validator" in build_script


def test_windows_build_targets_v2_release_without_blocking_automation():
    build_script = read_project_file("scripts/build.bat")

    assert 'set "VERSION=2.0.0"' in build_script
    assert 'if not "%NO_PAUSE%"=="1" pause' in build_script

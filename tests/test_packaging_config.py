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


def test_windows_build_archives_release_folder_without_renaming_locked_directory():
    build_script = read_project_file("scripts/build.bat")

    assert 'xcopy /E /I /Y "%TARGET_DIR%\\*" "%ARCHIVE_DIR%\\%PACKAGE_NAME%\\" >nul' in build_script
    assert 'move /Y "%TARGET_DIR%" "%ARCHIVE_DIR%\\" >nul' not in build_script


def test_windows_build_creates_zip_from_clean_staging_directory():
    build_script = read_project_file("scripts/build.bat")

    assert 'set "STAGING_DIR=%ROOT_DIR%\\tmp\\release_stage_%BUILD_STAMP%\\%PACKAGE_NAME%"' in build_script
    assert "Compress-Archive -Path '%STAGING_DIR%\\*'" in build_script


def test_windows_build_preserves_runtime_template_catalog_when_republishing_target_dir():
    build_script = read_project_file("scripts/build.bat")

    assert 'set "PRESERVED_TEMPLATES=%ROOT_DIR%\\tmp\\release_preserve_%BUILD_STAMP%_templates.json"' in build_script
    assert 'copy /Y "%TARGET_DIR%\\data\\templates.json" "%PRESERVED_TEMPLATES%" >nul' in build_script
    assert 'copy /Y "%PRESERVED_TEMPLATES%" "%TARGET_DIR%\\data\\templates.json" >nul' in build_script


def test_repository_and_release_package_declare_apache_license():
    license_text = read_project_file("LICENSE")
    readme = read_project_file("README.md")
    readme_zh = read_project_file("README.zh-CN.md")
    third_party_notices = read_project_file("THIRD_PARTY_NOTICES.md")
    build_script = read_project_file("scripts/build.bat")

    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "License: Apache-2.0" in readme
    assert "License: Apache-2.0" in readme_zh
    assert "Direct Python Dependencies" in third_party_notices

    assert '"%ROOT_DIR%\\LICENSE"' in build_script
    assert '"%ROOT_DIR%\\README.zh-CN.md"' in build_script
    assert '"%ROOT_DIR%\\THIRD_PARTY_NOTICES.md"' in build_script


def test_windows_build_bundles_seed_template_catalog():
    build_script = read_project_file("scripts/build.bat")
    config_module = read_project_file("backend/config.py")

    assert '--add-data "data\\templates.json;data"' in build_script
    assert '"%ROOT_DIR%\\data\\templates.json"' in build_script
    assert '"%STAGING_DIR%\\data\\templates.json"' in build_script
    assert '("data/templates.json", "data/templates.json")' in config_module

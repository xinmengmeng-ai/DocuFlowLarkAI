from pathlib import Path


TEST_FULL_FLOW = Path(__file__).parent / "test_full_flow.py"
TEST_IMPORT_API = Path(__file__).parent / "test_import_api.py"
TEST_TEMPLATE_IMPORT_EXPORT = Path(__file__).parent / "test_template_import_export.py"


def test_live_tests_require_explicit_opt_in():
    full_flow = TEST_FULL_FLOW.read_text(encoding="utf-8")
    import_api = TEST_IMPORT_API.read_text(encoding="utf-8")
    template_import_export = TEST_TEMPLATE_IMPORT_EXPORT.read_text(encoding="utf-8")

    assert "DOCUFLOW_RUN_LIVE_TESTS" in full_flow
    assert "DOCUFLOW_RUN_LIVE_TESTS" in import_api
    assert "DOCUFLOW_RUN_LIVE_TESTS" in template_import_export
    assert "pytestmark = pytest.mark.skipif" in full_flow
    assert "pytestmark = pytest.mark.skipif" in import_api
    assert "pytestmark = pytest.mark.skipif" in template_import_export


def test_live_node_mutation_requires_explicit_space_id():
    full_flow = TEST_FULL_FLOW.read_text(encoding="utf-8")
    template_import_export = TEST_TEMPLATE_IMPORT_EXPORT.read_text(encoding="utf-8")

    assert "DOCUFLOW_LIVE_TEST_SPACE_ID" in full_flow
    assert 'spaces[0]["space_id"]' not in full_flow
    assert "Path(__file__).parent / \"temp_import.json\"" not in template_import_export
    assert "TMP_DIR / \"temp_import.json\"" in template_import_export

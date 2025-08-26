"""
Unit tests for Salt issue #68204: regex in kernelpkg latest_available() fails on Debian Bullseye / Ubuntu Noble

This test file specifically tests the fix for the regex pattern in kernelpkg_linux_apt.latest_available()
that was failing on modern Debian and Ubuntu systems.
"""

import pytest

try:
    import salt.modules.kernelpkg_linux_apt as kernelpkg
    from tests.support.mock import MagicMock, patch

    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False


@pytest.fixture
def configure_loader_modules():
    """Fixture to configure the loader modules for testing"""
    return {
        kernelpkg: {
            "__grains__": {"kernelrelease": "6.1.0-38-cloud-amd64"},
            "__salt__": {
                "pkg.install": MagicMock(return_value={}),
                "pkg.latest_version": MagicMock(return_value=""),
                "pkg.list_pkgs": MagicMock(return_value={}),
                "pkg.purge": MagicMock(return_value=None),
                "system.reboot": MagicMock(return_value=None),
            },
        }
    }


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_debian_bookworm_format():
    """
    Test - Debian 12 (Bookworm) version format: 6.1.147-1
    This was one of the main failing cases in the bug report
    """
    # Mock pkg.latest_version to return Debian Bookworm format
    mock_latest_version = MagicMock(return_value="6.1.147-1")
    mock_latest_installed = MagicMock(return_value="6.1.0-38-cloud-amd64")
    
    with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
        with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
            result = kernelpkg.latest_available()
            
            # Should not crash and should return a properly formatted version
            assert isinstance(result, str)
            assert "6.1.147" in result
            assert "cloud-amd64" in result  # kernel type should be preserved


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_ubuntu_noble_format():
    """
    Test - Ubuntu 24.04 (Noble) version format: 6.8.0-45-generic
    This was the other main failing case mentioned in the bug report
    """
    # Mock pkg.latest_version to return Ubuntu Noble format
    mock_latest_version = MagicMock(return_value="6.8.0-45-generic")
    mock_latest_installed = MagicMock(return_value="6.1.0-38-generic")
    
    # Mock kernel type to return "generic" for this test
    with patch.object(kernelpkg, "_kernel_type", return_value="generic"):
        with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
            with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
                result = kernelpkg.latest_available()
                
                # Should not crash and should return a properly formatted version
                assert isinstance(result, str)
                assert "6.8.0" in result
                assert "45" in result
                assert "generic" in result


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_debian_bullseye_format():
    """
    Test - Debian 11 (Bullseye) version format: 5.10.0-18-amd64
    """
    mock_latest_version = MagicMock(return_value="5.10.0-18-amd64")
    mock_latest_installed = MagicMock(return_value="5.10.0-17-amd64")
    
    with patch.object(kernelpkg, "_kernel_type", return_value="amd64"):
        with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
            with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
                result = kernelpkg.latest_available()
                
                assert isinstance(result, str)
                assert "5.10.0" in result
                assert "18" in result
                assert "amd64" in result


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_ubuntu_jammy_format():
    """
    Test - Ubuntu 22.04 (Jammy) version format: 5.15.0-91-generic
    """
    mock_latest_version = MagicMock(return_value="5.15.0-91-generic")
    mock_latest_installed = MagicMock(return_value="5.15.0-90-generic")
    
    with patch.object(kernelpkg, "_kernel_type", return_value="generic"):
        with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
            with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
                result = kernelpkg.latest_available()
                
                assert isinstance(result, str)
                assert "5.15.0" in result
                assert "91" in result
                assert "generic" in result


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_debian_security_update_format():
    """
    Test - Debian security update format: 6.1.147-1+deb12u1
    """
    mock_latest_version = MagicMock(return_value="6.1.147-1+deb12u1")
    mock_latest_installed = MagicMock(return_value="6.1.0-38-cloud-amd64")
    
    with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
        with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
            result = kernelpkg.latest_available()
            
            assert isinstance(result, str)
            assert "6.1.147" in result
            # The security update suffix should be handled gracefully


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_ubuntu_complex_format():
    """
    Test - Ubuntu complex version format: 5.15.0-91.101-generic
    """
    mock_latest_version = MagicMock(return_value="5.15.0-91.101-generic")
    mock_latest_installed = MagicMock(return_value="5.15.0-90-generic")
    
    with patch.object(kernelpkg, "_kernel_type", return_value="generic"):
        with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
            with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
                result = kernelpkg.latest_available()
                
                assert isinstance(result, str)
                assert "5.15.0" in result
                assert "91" in result
                assert "generic" in result


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_backport_format():
    """
    Test - Debian backport format: 6.1.147-1~bpo11+1
    """
    mock_latest_version = MagicMock(return_value="6.1.147-1~bpo11+1")
    mock_latest_installed = MagicMock(return_value="5.10.0-18-amd64")
    
    with patch.object(kernelpkg, "_kernel_type", return_value="amd64"):
        with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
            with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
                result = kernelpkg.latest_available()
                
                assert isinstance(result, str)
                assert "6.1.147" in result
                # Backport suffix should be handled gracefully


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_empty_result_fallback():
    """
    Test - When pkg.latest_version returns empty string, should fallback to latest_installed
    """
    mock_latest_version = MagicMock(return_value="")
    mock_latest_installed = MagicMock(return_value="6.1.0-38-cloud-amd64")
    
    with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
        with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
            result = kernelpkg.latest_available()
            
            assert result == "6.1.0-38-cloud-amd64"


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_malformed_version_fallback():
    """
    Test - When version format is completely malformed, should fallback to latest_installed
    """
    mock_latest_version = MagicMock(return_value="not-a-version-at-all")
    mock_latest_installed = MagicMock(return_value="6.1.0-38-cloud-amd64")
    
    with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
        with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
            result = kernelpkg.latest_available()
            
            assert result == "6.1.0-38-cloud-amd64"


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
def test_issue_68204_original_error_reproduction():
    """
    Test - Reproduce the original AttributeError that would have occurred with old code
    This test demonstrates that the issue is fixed by ensuring no AttributeError occurs
    """
    # These are the exact version formats that caused the original issue
    failing_versions = [
        "6.1.147-1",      # Debian Bullseye/Bookworm
        "6.8.0-45-generic",  # Ubuntu Noble
    ]
    
    for version in failing_versions:
        mock_latest_version = MagicMock(return_value=version)
        mock_latest_installed = MagicMock(return_value="6.1.0-38-cloud-amd64")
        
        with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
            with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
                # This line would have caused AttributeError with the old regex
                # Now it should work without any exception
                try:
                    result = kernelpkg.latest_available()
                    # If we get here, the fix is working
                    assert isinstance(result, str)
                except AttributeError as e:
                    if "'NoneType' object has no attribute 'group'" in str(e):
                        pytest.fail(f"Original bug still present for version {version}: {e}")
                    else:
                        # Some other AttributeError, re-raise
                        raise


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
@pytest.mark.parametrize("version_string,description", [
    ("6.1.147-1", "Debian 12 Bookworm"),
    ("6.8.0-45-generic", "Ubuntu 24.04 Noble"),
    ("6.1.0-18-amd64", "Debian 11 Bullseye"),
    ("6.2.0-37-generic", "Ubuntu 23.04 Lunar"),
    ("5.15.0-91-generic", "Ubuntu 22.04 Jammy"),
    ("6.1.147-1+deb12u1", "Debian security update"),
])
def test_issue_68204_comprehensive_format_validation(version_string, description):
    """
    Test - Comprehensive validation that all reported problematic formats now work
    This test validates the complete fix using the actual problematic version strings
    """
    mock_latest_version = MagicMock(return_value=version_string)
    mock_latest_installed = MagicMock(return_value="6.1.0-38-cloud-amd64")
    
    with patch.dict(kernelpkg.__salt__, {"pkg.latest_version": mock_latest_version}):
        with patch.object(kernelpkg, "latest_installed", mock_latest_installed):
            # This should NOT raise an AttributeError anymore
            result = kernelpkg.latest_available()
            
            # Validate that we get a string result (no crash)
            assert isinstance(result, str), f"Failed for {description} format: {version_string}"
            
            # Validate that result is not empty
            assert len(result) > 0, f"Empty result for {description} format: {version_string}"

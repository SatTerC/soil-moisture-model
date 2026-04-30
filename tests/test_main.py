"""Tests for main module."""


def test_main():
    """Test that main function returns expected output."""
    from soil_moisture_model.main import main

    result = main()
    assert isinstance(result, str)
    assert "soil_moisture_model" in result

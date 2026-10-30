import soil_moisture_model


def test_version():
    assert isinstance(soil_moisture_model.__version__, str)

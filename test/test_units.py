from nose.tools import assert_raises, raises, with_setup
from starorbit.units import *


@raises(AssertionError)
def test_meters_add():
    meters(3) + degrees(3)

@raises(AssertionError)
def test_meters_sub():
    meters(3) - 4

def test_meters_ok():
    meters(1) + meters(4) - meters(3)


@raises(AssertionError)
def test_radians_add():
    radians(3) + degrees(3)

@raises(AssertionError)
def test_radians_sub():
    radians(3) - 4

def test_radians_ok():
    radians(1) + radians(4) - radians(3)

def test_radians_to_degs():
    d = radians(1).degrees
    assert isinstance(d, degrees)
    assert 57 < d < 58


@raises(AssertionError)
def test_degrees_add():
    degrees(3) + radians(3)

@raises(AssertionError)
def test_degrees_sub():
    degrees(3) - 4

def test_degrees_ok():
    d = degrees(1) + degrees(4) - degrees(3)
    assert isinstance(d, degrees)

def test_degrees_overflow():
    a = degrees(350) + degrees(90)
    assert a == 80

def test_degrees_underflow():
    a = degrees(50) - degrees(190)
    assert a == 220

def test_degrees_to_radians():
    r = degrees(90).radians
    assert isinstance(r, radians)
    assert 1.57 < r < 1.58

def test_degrees_opposite():
    d = degrees(45).opposite
    assert d == 225


def test_degrees_per_sec():
    dps = degrees_per_sec(2) * 3
    assert isinstance(dps, degrees_per_sec), type(dps)
    d = degrees_per_sec(2) * seconds(3)
    assert isinstance(d, degrees)


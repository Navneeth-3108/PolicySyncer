import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer1.modals import detect_modals, is_definitional


def test_basic_obligation():
    m = detect_modals("Employees must rotate passwords.")
    assert len(m) == 1
    assert m[0].normalized == "OBLIGATION"
    assert m[0].polarity == "POSITIVE"
    assert m[0].strength == 3


def test_negated_multiword_before_singleword():
    # "must not" should match PROHIBITION, not OBLIGATION "must"
    m = detect_modals("Employees must not reuse passwords.")
    assert len(m) == 1
    assert m[0].normalized == "PROHIBITION"
    assert m[0].polarity == "NEGATIVE"


def test_may_not_followed_by_not_is_prohibition_not_permission():
    m = detect_modals("Previous 10 passwords may not be reused.")
    assert len(m) == 1
    assert m[0].normalized == "PROHIBITION"


def test_bare_may_is_permission():
    m = detect_modals("Employees may use a password manager.")
    assert len(m) == 1
    assert m[0].normalized == "PERMISSION"
    assert m[0].strength == 1


def test_should_not_is_prohibition_strength_2():
    m = detect_modals("Users should not share credentials.")
    assert m[0].normalized == "PROHIBITION"
    assert m[0].strength == 2


def test_split_negation_detected():
    # "must, under no circumstances, not be reused" — negation is >0 tokens
    # away from the modal itself.
    text = "Passwords must, under no circumstances, not be reused."
    m = detect_modals(text)
    assert len(m) == 1
    assert m[0].split_negation is True
    assert m[0].normalized == "PROHIBITION"


def test_definitional_shall_is_not_an_obligation():
    text = "This policy shall be known as the Acceptable Use Policy."
    assert is_definitional(text)
    assert detect_modals(text) == []


def test_shall_mean_is_definitional():
    text = "The term 'credential' shall mean any secret used for authentication."
    assert detect_modals(text) == []


def test_two_modals_in_one_sentence():
    text = "Employees must rotate passwords every 90 days and must not reuse the last 5 passwords."
    m = detect_modals(text)
    assert len(m) == 2
    assert m[0].normalized == "OBLIGATION"
    assert m[1].normalized == "PROHIBITION"

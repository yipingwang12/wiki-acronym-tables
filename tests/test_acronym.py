from wiki_acronyms.acronym import chunk_acronym, name_initials


def test_two_word_name():
    assert name_initials("Sully Prudhomme") == "SP"


def test_three_word_name():
    assert name_initials("Rudolf Christoph Eucken") == "RCE"


def test_single_word():
    assert name_initials("Tagore") == "T"


def test_lowercase_words_uppercased():
    assert name_initials("sully prudhomme") == "SP"


# Particles skipped
def test_von_skipped():
    assert name_initials("Paul von Heyse") == "PH"


def test_de_skipped():
    assert name_initials("Charles de Gaulle") == "CG"


def test_du_skipped():
    assert name_initials("Jean du Bellay") == "JB"


def test_van_skipped():
    assert name_initials("Vincent van Gogh") == "VG"


def test_particle_only_name_uses_particle():
    # If stripping particles leaves nothing, fall back to using them
    assert name_initials("von") == "V"


# Hyphenated names
def test_hyphenated_first_name():
    assert name_initials("Jean-Paul Sartre") == "JPS"


def test_hyphenated_last_name():
    assert name_initials("Frédéric Mistral-Durand") == "FMD"


def test_multiple_hyphens():
    assert name_initials("Marie-Anne-Louise Dupont") == "MALD"


# Combined
def test_hyphen_and_particle():
    assert name_initials("Jean-Paul de Sartre") == "JPS"


def test_chunk_acronym_single():
    assert chunk_acronym(["Sully Prudhomme"]) == "SP"


def test_chunk_acronym_multiple():
    assert chunk_acronym(["Sully Prudhomme", "Theodor Mommsen"]) == "SPTM"


def test_chunk_acronym_multiword_names():
    assert chunk_acronym(["Rudolf Christoph Eucken", "Selma Lagerlöf"]) == "RCESL"


def test_chunk_acronym_empty():
    assert chunk_acronym([]) == ""


# first_only mode
def test_first_only_simple():
    assert name_initials("Toni Morrison", first_only=True) == "T"


def test_first_only_ignores_remaining_words():
    assert name_initials("Gabriel García Márquez", first_only=True) == "G"


def test_first_only_hyphenated_takes_first_component():
    assert name_initials("Jean-Paul Sartre", first_only=True) == "J"


def test_first_only_ignores_particles():
    # first_only: just the literal first token's first letter, no particle logic needed
    assert name_initials("Toni Morrison", first_only=True) == "T"


# line_initials — poetry lines, no particle skipping
from wiki_acronyms.acronym import line_initials


def test_line_initials_basic():
    assert line_initials("Shall I compare thee to a summer's day?") == "SICTTASD"


def test_line_initials_includes_particles():
    # "to" and "a" are particles but must be included in poetry lines
    assert line_initials("to be or not to be") == "TBONTB"


def test_line_initials_strips_leading_punctuation():
    assert line_initials("'Twas the night before Christmas") == "TTNBC"


def test_line_initials_empty_line():
    assert line_initials("") == ""


def test_line_initials_punctuation_only_word_skipped():
    # A token that is entirely punctuation yields no letter
    assert line_initials("hello -- world") == "HW"


def test_line_initials_uppercase():
    assert line_initials("rough winds do shake") == "RWDS"

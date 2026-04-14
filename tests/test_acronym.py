from wiki_acronyms.acronym import chunk_acronym, name_initials


def test_two_word_name():
    assert name_initials("Sully Prudhomme") == "SP"


def test_three_word_name():
    assert name_initials("Rudolf Christoph Eucken") == "RCE"


def test_single_word():
    assert name_initials("Tagore") == "T"


def test_lowercase_words_uppercased():
    assert name_initials("sully prudhomme") == "SP"


def test_chunk_acronym_single():
    assert chunk_acronym(["Sully Prudhomme"]) == "SP"


def test_chunk_acronym_multiple():
    assert chunk_acronym(["Sully Prudhomme", "Theodor Mommsen"]) == "SPTM"


def test_chunk_acronym_multiword_names():
    assert chunk_acronym(["Rudolf Christoph Eucken", "Selma Lagerlöf"]) == "RCESL"


def test_chunk_acronym_empty():
    assert chunk_acronym([]) == ""

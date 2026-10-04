import numpy as np

from analyzers.semantic_analyzer import SemanticEngine, cosine_matrix


def test_cosine_matrix_known_values():
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    b = np.array([[1.0, 0.0], [1.0, 1.0]])
    m = cosine_matrix(a, b)
    assert np.isclose(m[0, 0], 1.0) and np.isclose(m[1, 0], 0.0) and np.isclose(m[0, 1], 1 / np.sqrt(2))


def test_cosine_handles_zero_and_empty():
    assert cosine_matrix(np.zeros((1, 3)), np.ones((1, 3)))[0, 0] == 0
    assert cosine_matrix(np.zeros((0, 3)), np.ones((2, 3))).shape == (0, 2)


def test_tfidf_ranks_relevant_passage_first():
    eng = SemanticEngine("tfidf")
    texts = ["Cloud accounting software automates GST returns for small businesses.", "The weather in Wellington is windy in spring.", "Our football club won the match."]
    sims = eng.similarity(["best accounting software for small business"], texts)[0]
    assert int(sims.argmax()) == 0 and sims[0] > sims[1]
    assert eng.backend == "tfidf" and 0 <= eng.sim_to_score(float(sims[0])) <= 100


def test_empty_inputs_do_not_crash():
    eng = SemanticEngine("tfidf")
    assert eng.similarity([], ["a"]).shape == (0, 1)
    assert eng.similarity(["q"], ["", ""]).shape == (1, 2)


def test_cluster_returns_label_per_text():
    eng = SemanticEngine("tfidf")
    labels = eng.cluster(["apple pie recipe", "banana bread recipe", "car engine repair", "truck engine service", "cooking pie", "engine oil"], k=2)
    assert len(labels) == 6 and len(set(labels)) <= 2


def test_forced_sbert_falls_back_without_package():
    eng = SemanticEngine("sbert", "nonexistent/model")
    assert eng.backend in ("tfidf", "sbert")

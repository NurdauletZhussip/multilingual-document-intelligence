"""Fit a character n-gram intent classifier from the bundled labelled examples."""

import json
import re
import unicodedata
from collections import Counter
from importlib.resources import files

import numpy as np


def features(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    counts = Counter()
    for word in re.findall(r"[^\W_]+", text):
        counts[f"word={word}"] += 1
        padded = f"^{word}$"
        for size in (2, 3, 4):
            counts.update(padded[i:i + size] for i in range(len(padded) - size + 1))
    return counts


class FieldModel:
    """Regularized least squares on cosine kernels over TF-IDF features."""

    def __init__(self):
        samples = json.loads(files(__package__).joinpath("training.json").read_text("utf-8"))
        self.labels = list(samples)
        rows = [(features(phrase), label) for label, phrases in samples.items() for phrase in phrases]
        frequency = Counter(key for grams, _ in rows for key in grams)
        self.columns = {key: i for i, key in enumerate(frequency)}
        self.idf = np.log((1 + len(rows)) / (1 + np.array(list(frequency.values())))) + 1
        self.train = np.stack([self.vector(grams) for grams, _ in rows])
        targets = np.eye(len(samples))[[self.labels.index(label) for _, label in rows]]
        kernel = self.train @ self.train.T
        self.weights = np.linalg.solve(kernel + 0.35 * np.eye(len(rows)), targets)

    def vector(self, grams):
        row = np.zeros(len(self.columns))
        for key, count in grams.items():
            if key in self.columns:
                row[self.columns[key]] = (1 + np.log(count)) * self.idf[self.columns[key]]
        return row / max(np.linalg.norm(row), 1e-12)

    def classify(self, text, min_similarity=0.0):
        similarity = self.train @ self.vector(features(text))
        if similarity.max() < min_similarity:
            return None
        scores = similarity @ self.weights
        first, second = np.argsort(scores)[-2:][::-1]
        label = self.labels[first]
        # These gates allow unknown wording and competing intents to abstain.
        if scores[first] < 0.27 or scores[first] - scores[second] < 0.09 or label == "other":
            return None
        return label

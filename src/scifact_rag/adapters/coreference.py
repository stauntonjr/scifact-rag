from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..domain import CoreferenceAnalysis, CoreferenceMention, SentenceSpan


class FastCorefAnalyzer:
    def __init__(
        self,
        model_name: str = "biu-nlp/f-coref",
        *,
        device: str = "cpu",
        max_tokens_in_batch: int = 4000,
    ) -> None:
        if max_tokens_in_batch < 1:
            raise ValueError("max_tokens_in_batch must be positive")
        self._model_name = model_name
        self._device = device
        self._max_tokens_in_batch = max_tokens_in_batch
        self._model: Any | None = None
        self._nlp: Any | None = None

    def analyze(self, texts: Sequence[str]) -> list[CoreferenceAnalysis]:
        nlp = self._load_nlp()
        model = self._load_model(nlp)
        predictions = model.predict(
            texts=list(texts),
            max_tokens_in_batch=self._max_tokens_in_batch,
        )
        analyses: list[CoreferenceAnalysis] = []
        for text, prediction in zip(texts, predictions, strict=True):
            document = nlp(text)
            clusters: list[tuple[CoreferenceMention, ...]] = []
            for raw_cluster in prediction.get_clusters(as_strings=False):
                mentions: list[CoreferenceMention] = []
                for start, end in raw_cluster:
                    span = document.char_span(start, end, alignment_mode="expand")
                    if span is None:
                        continue
                    mentions.append(
                        CoreferenceMention(
                            start=start,
                            end=end,
                            text=text[start:end],
                            pos_tags=tuple(token.pos_ for token in span),
                            is_possessive=any("Yes" in token.morph.get("Poss") for token in span),
                        )
                    )
                if len(mentions) > 1:
                    clusters.append(tuple(mentions))
            prediction.release_logits()
            analyses.append(CoreferenceAnalysis(text=text, clusters=tuple(clusters)))
        return analyses

    def sentences(self, text: str) -> list[str]:
        return [sentence.text for sentence in self.sentence_spans(text)]

    def sentence_spans(self, text: str) -> list[SentenceSpan]:
        document = self._load_nlp()(text)
        return [
            SentenceSpan(sentence.start_char, sentence.end_char, sentence.text.strip())
            for sentence in document.sents
            if sentence.text.strip()
        ]

    def _load_nlp(self) -> Any:
        if self._nlp is None:
            import spacy

            self._nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "textcat"])
        return self._nlp

    def _load_model(self, nlp: Any) -> Any:
        if self._model is None:
            from fastcoref import FCoref

            self._model = FCoref(
                model_name_or_path=self._model_name,
                device=self._device,
                nlp=nlp,
                enable_progress_bar=False,
            )
        return self._model

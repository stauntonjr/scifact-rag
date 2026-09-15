from __future__ import annotations

import os
from dataclasses import dataclass

from .adapters.coreference import FastCorefAnalyzer
from .adapters.minilm import MiniLmEmbedder
from .adapters.openai_compatible import (
    SCIFACT_EVALUATION_SEED,
    GenerationPromptProfile,
    OpenAiCompatibleGenerator,
)
from .adapters.postgres import PostgresEvidenceStore
from .adapters.proposition_extraction import (
    PROPOSITION_PROMPT_ID,
    PROPOSITION_PROMPT_SHA256,
    PROPOSITION_SCHEMA_SHA256,
    PROPOSITION_SEED,
    OpenAiCompatiblePropositionExtractor,
)
from .adapters.reranker import RankLlmReranker, TeiReranker, VllmColbertReranker
from .adapters.scientific_inference import TransformersScientificInferenceClient
from .adapters.tokenization import HuggingFacePairTokenBudget, HuggingFaceTokenBudget
from .application import RagApplication
from .generation import (
    DpChunkContextAssembler,
    GenerationContextStrategyName,
    WholeDocumentContextAssembler,
)
from .generation_evaluation import PairedGenerationEvaluator
from .proposition_evaluation import PropositionEvaluationExecutor, PropositionSourceManifest
from .retrievers import (
    Bm25CandidateGenerator,
    Bm25CandidateScorer,
    Bm25Retriever,
    EqualScoreFusionPolicy,
    IdentityScoreNormalizer,
    KeywordRetriever,
    PooledRankingRetriever,
    ReciprocalRankAggregator,
    ReciprocalRankFusionRetriever,
    RerankerCandidateScorer,
    RerankingRetriever,
    RobustScoreNormalizer,
    StoredChunkMaxRerankerCandidateScorer,
    TitleRerankerCandidateScorer,
    VectorCandidateGenerator,
    VectorCandidateScorer,
    VectorRetriever,
)
from .scientific_inference import (
    DEBERTA_MODEL,
    DEBERTA_REVISION,
    ScientificEvidenceAssembler,
)
from .scientific_inference_evaluation import (
    ScientificInferenceEvaluationExecutor,
    ScientificInferenceEvaluator,
    ScientificInferenceRunManifest,
)
from .strategies import (
    COREF_NOMINAL_DP_COLBERT,
    COREF_NOMINAL_DP_MINILM,
    DEFAULT_RETRIEVAL_STRATEGY,
    CanonicalizationPolicy,
    CompositeRepresentationStrategy,
    CoreferenceIntervalPackingStrategy,
    CoreferenceNominalDpStrategy,
    CoreferenceSentenceStrategy,
    DocumentOnlyStrategy,
    DpBoundaryProfile,
    RetrievalStrategyName,
    SentencePackingStrategy,
    TitleStrategy,
    TokenWindowStrategy,
    bm25_fusion_vector_strategy,
    coreference_policies,
    pooled_incremental_vector_strategy,
    pooled_single_reranker,
)

_COLBERT_REVISION = "c72aa89bc61afdd85373643f3a1a75b2aad6e0fe"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    embedding_model: str
    generator_base_url: str
    generator_model: str
    generator_api_key: str | None
    coreference_model: str
    coreference_device: str
    coreference_max_tokens: int
    reranker_base_url: str
    late_interaction_base_url: str
    late_interaction_model: str
    rank_llm_base_url: str
    scientific_inference_base_url: str = "http://scientific-inference:80"
    scientific_inference_model: str = DEBERTA_MODEL
    scientific_inference_revision: str = DEBERTA_REVISION
    scientific_inference_max_tokens: int = 512

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://scifact:scifact@postgres:5432/scifact",
            ),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-MiniLM-L6-v2",
            ),
            generator_base_url=os.getenv(
                "GENERATOR_BASE_URL", "http://host.docker.internal:8000/v1"
            ),
            generator_model=os.getenv("GENERATOR_MODEL", "nvidia/Qwen3.6-35B-A3B-NVFP4"),
            generator_api_key=os.getenv("GENERATOR_API_KEY"),
            coreference_model=os.getenv("COREFERENCE_MODEL", "biu-nlp/f-coref"),
            coreference_device=os.getenv("COREFERENCE_DEVICE", "cpu"),
            coreference_max_tokens=int(os.getenv("COREFERENCE_MAX_TOKENS", "4000")),
            reranker_base_url=os.getenv("RERANKER_BASE_URL", "http://reranker:80"),
            late_interaction_base_url=os.getenv(
                "LATE_INTERACTION_BASE_URL", "http://late-interaction:80"
            ),
            late_interaction_model=os.getenv(
                "LATE_INTERACTION_MODEL",
                "answerdotai/answerai-colbert-small-v1",
            ),
            rank_llm_base_url=os.getenv("RANK_LLM_BASE_URL", "http://rankllm:80"),
            scientific_inference_base_url=os.getenv(
                "SCIENTIFIC_INFERENCE_BASE_URL", "http://scientific-inference:80"
            ),
            scientific_inference_model=os.getenv("SCIENTIFIC_INFERENCE_MODEL", DEBERTA_MODEL),
            scientific_inference_revision=os.getenv(
                "SCIENTIFIC_INFERENCE_REVISION", DEBERTA_REVISION
            ),
            scientific_inference_max_tokens=int(
                os.getenv("SCIENTIFIC_INFERENCE_MAX_TOKENS", "512")
            ),
        )


def build_application(
    settings: Settings | None = None,
    *,
    retrieval_strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY,
    generation_context_strategy: GenerationContextStrategyName = (
        GenerationContextStrategyName.WHOLE_DOCUMENT
    ),
) -> RagApplication:
    resolved = settings or Settings.from_environment()
    store = PostgresEvidenceStore(resolved.database_url)
    fusion_vector_strategy = bm25_fusion_vector_strategy(retrieval_strategy)
    incremental_pool_strategy = pooled_incremental_vector_strategy(retrieval_strategy)
    single_reranker = pooled_single_reranker(retrieval_strategy)
    vector_strategy = fusion_vector_strategy or retrieval_strategy
    embedder = (
        None
        if retrieval_strategy in (RetrievalStrategyName.KEYWORD, RetrievalStrategyName.BM25)
        else MiniLmEmbedder(resolved.embedding_model)
    )
    if retrieval_strategy in (RetrievalStrategyName.KEYWORD, RetrievalStrategyName.BM25):
        strategy = DocumentOnlyStrategy(retrieval_strategy)
        retriever = (
            Bm25Retriever(store)
            if retrieval_strategy is RetrievalStrategyName.BM25
            else KeywordRetriever(store)
        )
    elif retrieval_strategy in (
        RetrievalStrategyName.POOLED_COREF_NOMINAL_DP_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RAW_MEAN_COLBERT,
    ):
        assert embedder is not None
        analyzer = FastCorefAnalyzer(
            resolved.coreference_model,
            device=resolved.coreference_device,
            max_tokens_in_batch=resolved.coreference_max_tokens,
        )
        minilm_budget = HuggingFaceTokenBudget(
            resolved.embedding_model,
            maximum_content_tokens=126,
        )
        colbert_budget = HuggingFaceTokenBudget(
            resolved.late_interaction_model,
            maximum_content_tokens=510,
            revision=_COLBERT_REVISION,
        )
        title_strategy = TitleStrategy()
        nominal_dp_strategy = CoreferenceNominalDpStrategy(
            analyzer,
            DpBoundaryProfile(
                COREF_NOMINAL_DP_MINILM,
                minilm_budget.content_token_count,
                minilm_budget.bounded_source_windows,
                target_tokens=112,
                maximum_tokens=126,
                embedding_required=True,
            ),
            DpBoundaryProfile(
                COREF_NOMINAL_DP_COLBERT,
                colbert_budget.content_token_count,
                colbert_budget.bounded_source_windows,
                target_tokens=510,
                maximum_tokens=510,
                embedding_required=False,
            ),
        )
        if retrieval_strategy is RetrievalStrategyName.POOLED_COREF_NOMINAL_DP_COLBERT:
            strategy = CompositeRepresentationStrategy(
                retrieval_strategy.value,
                (title_strategy, nominal_dp_strategy),
            )
            generators = (
                Bm25CandidateGenerator(store),
                VectorCandidateGenerator("title", store, embedder, title_strategy.representations),
                VectorCandidateGenerator(
                    "coref-nominal",
                    store,
                    embedder,
                    ("coref-nominal-sentence",),
                ),
                VectorCandidateGenerator(
                    "coref-nominal-dp",
                    store,
                    embedder,
                    (COREF_NOMINAL_DP_MINILM,),
                ),
            )
        else:
            token_strategy = TokenWindowStrategy(embedder.token_windows)
            proper_noun_strategy = CoreferenceSentenceStrategy(
                analyzer,
                (CanonicalizationPolicy.PROPER_NOUN,),
            )
            interval_strategy = _build_packing_strategy(
                RetrievalStrategyName.COREF_INTERVAL_PACK,
                analyzer,
                embedder,
            )
            strategy = CompositeRepresentationStrategy(
                retrieval_strategy.value,
                (
                    title_strategy,
                    token_strategy,
                    proper_noun_strategy,
                    nominal_dp_strategy,
                    interval_strategy,
                ),
            )
            generators = (
                Bm25CandidateGenerator(store),
                VectorCandidateGenerator("title", store, embedder, title_strategy.representations),
                VectorCandidateGenerator(
                    "token-window", store, embedder, token_strategy.representations
                ),
                VectorCandidateGenerator(
                    "coref-propn",
                    store,
                    embedder,
                    proper_noun_strategy.representations,
                ),
                VectorCandidateGenerator(
                    "coref-nominal",
                    store,
                    embedder,
                    ("coref-nominal-sentence",),
                ),
                VectorCandidateGenerator(
                    interval_strategy.name,
                    store,
                    embedder,
                    interval_strategy.representations,
                ),
            )
        colbert = VllmColbertReranker(
            resolved.late_interaction_base_url,
            resolved.late_interaction_model,
        )
        content_scorer = StoredChunkMaxRerankerCandidateScorer(
            "colbert-content",
            store,
            colbert,
            COREF_NOMINAL_DP_COLBERT,
        )
        scorers = (
            (content_scorer,)
            if retrieval_strategy is RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT
            else (TitleRerankerCandidateScorer("colbert-title", colbert), content_scorer)
        )
        normalizer = (
            IdentityScoreNormalizer()
            if retrieval_strategy
            in (
                RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
                RetrievalStrategyName.POOLED_COREF_INTERVAL_RAW_MEAN_COLBERT,
            )
            else RobustScoreNormalizer()
        )
        retriever = PooledRankingRetriever(
            generators,
            scorers,
            EqualScoreFusionPolicy(),
            normalizer=normalizer,
        )
    elif retrieval_strategy in (
        RetrievalStrategyName.RERANK_MSMARCO,
        RetrievalStrategyName.POOLED_FOUR_CHANNEL_RRF,
        RetrievalStrategyName.POOLED_MSMARCO_RRF,
        RetrievalStrategyName.POOLED_FOUR_CHANNEL_ROBUST_SUM,
        RetrievalStrategyName.POOLED_COLBERT,
        RetrievalStrategyName.POOLED_SENTENCE_PACK_RRF,
        RetrievalStrategyName.POOLED_COREF_AWARE_PACK_RRF,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_PACK_RRF,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MSMARCO,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR,
    ):
        assert embedder is not None
        analyzer = FastCorefAnalyzer(
            resolved.coreference_model,
            device=resolved.coreference_device,
            max_tokens_in_batch=resolved.coreference_max_tokens,
        )
        title_strategy = TitleStrategy()
        token_strategy = TokenWindowStrategy(embedder.token_windows)
        coreference_strategy = CoreferenceSentenceStrategy(
            analyzer,
            (
                CanonicalizationPolicy.PROPER_NOUN,
                CanonicalizationPolicy.EXPLICIT_NOMINAL,
            ),
        )
        representation_strategies = [title_strategy, token_strategy, coreference_strategy]
        channels = [
            ("title", title_strategy.representations),
            ("token-window", token_strategy.representations),
            ("coref-propn", ("coref-propn-sentence",)),
            ("coref-nominal", ("coref-nominal-sentence",)),
        ]
        if incremental_pool_strategy is not None:
            packing_strategy = _build_packing_strategy(
                incremental_pool_strategy,
                analyzer,
                embedder,
            )
            representation_strategies.append(packing_strategy)
            channels.append((packing_strategy.name, packing_strategy.representations))
        strategy = CompositeRepresentationStrategy(
            retrieval_strategy.value,
            representation_strategies,
        )
        if retrieval_strategy is RetrievalStrategyName.RERANK_MSMARCO:
            candidate_retrievers = (
                Bm25Retriever(store),
                *(
                    VectorRetriever(store, embedder, representations)
                    for _, representations in channels
                ),
            )
            retriever = RerankingRetriever(
                candidate_retrievers,
                TeiReranker(resolved.reranker_base_url),
            )
        else:
            generators = (
                Bm25CandidateGenerator(store),
                *(
                    VectorCandidateGenerator(name, store, embedder, representations)
                    for name, representations in channels
                ),
            )
            if single_reranker == "colbert":
                scorers = (
                    RerankerCandidateScorer(
                        "colbert",
                        VllmColbertReranker(
                            resolved.late_interaction_base_url,
                            resolved.late_interaction_model,
                        ),
                    ),
                )
            elif single_reranker == "msmarco":
                scorers = (
                    RerankerCandidateScorer(
                        "msmarco",
                        TeiReranker(resolved.reranker_base_url),
                    ),
                )
            elif single_reranker == "rankzephyr":
                scorers = (
                    RerankerCandidateScorer(
                        "rankzephyr",
                        RankLlmReranker(resolved.rank_llm_base_url),
                    ),
                )
            else:
                scorers = (
                    Bm25CandidateScorer(store),
                    *(
                        VectorCandidateScorer(name, store, embedder, representations)
                        for name, representations in channels
                    ),
                )
                if retrieval_strategy is RetrievalStrategyName.POOLED_MSMARCO_RRF:
                    scorers = (
                        *scorers,
                        RerankerCandidateScorer(
                            "msmarco",
                            TeiReranker(resolved.reranker_base_url),
                        ),
                    )
            robust_fusion = (
                retrieval_strategy is RetrievalStrategyName.POOLED_FOUR_CHANNEL_ROBUST_SUM
            )
            retriever = PooledRankingRetriever(
                generators,
                scorers,
                EqualScoreFusionPolicy() if robust_fusion else ReciprocalRankAggregator(),
                normalizer=RobustScoreNormalizer() if robust_fusion else None,
            )
    elif retrieval_strategy is RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF:
        assert embedder is not None
        title_strategy = TitleStrategy()
        token_strategy = TokenWindowStrategy(embedder.token_windows)
        strategy = CompositeRepresentationStrategy(
            retrieval_strategy.value,
            (title_strategy, token_strategy),
        )
        retriever = ReciprocalRankFusionRetriever(
            (
                VectorRetriever(store, embedder, title_strategy.representations),
                VectorRetriever(store, embedder, token_strategy.representations),
            )
        )
    elif vector_strategy in (
        RetrievalStrategyName.TOKEN_WINDOW,
        RetrievalStrategyName.SENTENCE_PACK,
        RetrievalStrategyName.COREF_AWARE_PACK,
        RetrievalStrategyName.COREF_INTERVAL_PACK,
    ):
        assert embedder is not None
        strategy = TokenWindowStrategy(embedder.token_windows)
        if vector_strategy is not RetrievalStrategyName.TOKEN_WINDOW:
            strategy = _build_packing_strategy(
                vector_strategy,
                FastCorefAnalyzer(
                    resolved.coreference_model,
                    device=resolved.coreference_device,
                    max_tokens_in_batch=resolved.coreference_max_tokens,
                ),
                embedder,
            )
        dense = VectorRetriever(store, embedder, strategy.representations)
        retriever = (
            ReciprocalRankFusionRetriever((dense, Bm25Retriever(store)))
            if fusion_vector_strategy is not None
            else dense
        )
    else:
        assert embedder is not None
        policies = (
            (CanonicalizationPolicy.PROPER_NOUN,)
            if retrieval_strategy is RetrievalStrategyName.HYBRID_RRF
            else coreference_policies(vector_strategy)
        )
        strategy = CoreferenceSentenceStrategy(
            FastCorefAnalyzer(
                resolved.coreference_model,
                device=resolved.coreference_device,
                max_tokens_in_batch=resolved.coreference_max_tokens,
            ),
            policies,
        )
        dense = VectorRetriever(store, embedder, strategy.representations)
        if retrieval_strategy is RetrievalStrategyName.HYBRID_RRF:
            retriever = ReciprocalRankFusionRetriever((dense, KeywordRetriever(store)))
        elif fusion_vector_strategy is not None:
            retriever = ReciprocalRankFusionRetriever((dense, Bm25Retriever(store)))
        else:
            retriever = dense
    context_assembler = (
        WholeDocumentContextAssembler()
        if generation_context_strategy is GenerationContextStrategyName.WHOLE_DOCUMENT
        else DpChunkContextAssembler(
            store,
            VllmColbertReranker(
                resolved.late_interaction_base_url,
                resolved.late_interaction_model,
            ),
            adaptive=True,
        )
    )
    return RagApplication(
        store=store,
        embedder=embedder,
        generator=OpenAiCompatibleGenerator(
            base_url=resolved.generator_base_url,
            model=resolved.generator_model,
            api_key=resolved.generator_api_key,
        ),
        strategy=strategy,
        retriever=retriever,
        context_assembler=context_assembler,
    )


class _ApplicationRetriever:
    def __init__(self, application: RagApplication) -> None:
        self._application = application

    def search(self, query: str, limit: int):
        return self._application.search(query, limit=limit)


def build_generation_evaluator(
    settings: Settings | None = None,
    *,
    retrieval_strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY,
) -> PairedGenerationEvaluator:
    resolved = settings or Settings.from_environment()
    retrieval_application = build_application(
        resolved,
        retrieval_strategy=retrieval_strategy,
        generation_context_strategy=GenerationContextStrategyName.WHOLE_DOCUMENT,
    )
    store = PostgresEvidenceStore(resolved.database_url)
    colbert = VllmColbertReranker(
        resolved.late_interaction_base_url,
        resolved.late_interaction_model,
    )
    return PairedGenerationEvaluator(
        retriever=_ApplicationRetriever(retrieval_application),
        assemblers={
            GenerationContextStrategyName.WHOLE_DOCUMENT: WholeDocumentContextAssembler(),
            GenerationContextStrategyName.ADAPTIVE: DpChunkContextAssembler(
                store,
                colbert,
                adaptive=True,
            ),
        },
        generator=OpenAiCompatibleGenerator(
            base_url=resolved.generator_base_url,
            model=resolved.generator_model,
            api_key=resolved.generator_api_key,
            prompt_profile=GenerationPromptProfile.SCIFACT_CLAIM_VERIFICATION,
            seed=SCIFACT_EVALUATION_SEED,
        ),
    )


def build_scientific_inference_executor(
    run_manifest: ScientificInferenceRunManifest,
    settings: Settings | None = None,
) -> ScientificInferenceEvaluationExecutor:
    resolved = settings or Settings.from_environment()
    runtime_boundary = {
        "endpoint": resolved.scientific_inference_base_url,
        "model": resolved.scientific_inference_model,
        "model_revision": resolved.scientific_inference_revision,
        "context_limit": resolved.scientific_inference_max_tokens,
        "colbert_model": resolved.late_interaction_model,
        "colbert_revision": _COLBERT_REVISION,
    }
    manifest_boundary = {
        "endpoint": run_manifest.endpoint,
        "model": run_manifest.model,
        "model_revision": run_manifest.model_revision,
        "context_limit": run_manifest.context_limit,
        "colbert_model": run_manifest.colbert_model,
        "colbert_revision": run_manifest.colbert_revision,
    }
    mismatched = [
        name for name, value in runtime_boundary.items() if value != manifest_boundary[name]
    ]
    if mismatched:
        raise ValueError(
            "scientific inference runtime does not match the run manifest: "
            + ", ".join(sorted(mismatched))
        )
    application = build_application(
        resolved,
        retrieval_strategy=DEFAULT_RETRIEVAL_STRATEGY,
        generation_context_strategy=GenerationContextStrategyName.WHOLE_DOCUMENT,
    )
    store = PostgresEvidenceStore(resolved.database_url)
    colbert = VllmColbertReranker(
        resolved.late_interaction_base_url,
        resolved.late_interaction_model,
    )
    pair_budget = HuggingFacePairTokenBudget(
        resolved.scientific_inference_model,
        resolved.scientific_inference_revision,
        maximum_pair_tokens=resolved.scientific_inference_max_tokens,
    )
    assembler = ScientificEvidenceAssembler(store, colbert, pair_budget)
    client = TransformersScientificInferenceClient(
        resolved.scientific_inference_base_url,
        resolved.scientific_inference_revision,
    )
    return ScientificInferenceEvaluationExecutor(
        application,
        ScientificInferenceEvaluator(assembler, client),
        store,
    )


def build_proposition_evaluator(
    manifest: PropositionSourceManifest,
    settings: Settings | None = None,
) -> tuple[PropositionEvaluationExecutor, MiniLmEmbedder]:
    resolved = settings or Settings.from_environment()
    extractor = build_proposition_extractor(manifest, resolved)
    return PropositionEvaluationExecutor(extractor), MiniLmEmbedder(resolved.embedding_model)


def build_proposition_extractor(
    manifest: PropositionSourceManifest,
    settings: Settings | None = None,
) -> OpenAiCompatiblePropositionExtractor:
    resolved = settings or Settings.from_environment()
    runtime = {
        "extractor_model": resolved.generator_model,
        "prompt_id": PROPOSITION_PROMPT_ID,
        "prompt_sha256": PROPOSITION_PROMPT_SHA256,
        "schema_sha256": PROPOSITION_SCHEMA_SHA256,
        "seed": PROPOSITION_SEED,
        "embedding_model": resolved.embedding_model,
    }
    mismatched = [name for name, value in runtime.items() if getattr(manifest, name) != value]
    if mismatched:
        raise ValueError(
            "proposition runtime does not match the source manifest: "
            + ", ".join(sorted(mismatched))
        )
    return OpenAiCompatiblePropositionExtractor(
        base_url=resolved.generator_base_url,
        model=resolved.generator_model,
        api_key=resolved.generator_api_key,
    )


def _build_packing_strategy(
    strategy: RetrievalStrategyName,
    analyzer: FastCorefAnalyzer,
    embedder: MiniLmEmbedder,
) -> SentencePackingStrategy:
    if strategy is RetrievalStrategyName.COREF_INTERVAL_PACK:
        return CoreferenceIntervalPackingStrategy(
            analyzer,
            embedder.content_token_count,
            embedder.bounded_token_windows,
        )
    if strategy not in (
        RetrievalStrategyName.SENTENCE_PACK,
        RetrievalStrategyName.COREF_AWARE_PACK,
    ):
        raise ValueError(f"{strategy.value} is not a sentence-packing strategy")
    return SentencePackingStrategy(
        analyzer,
        embedder.content_token_count,
        embedder.bounded_token_windows,
        coreference_aware=(strategy is RetrievalStrategyName.COREF_AWARE_PACK),
    )

"use client";

// Zustand store for the query flow: the question being asked, its mode,
// document scoping (for compare mode), the in-flight/completed answer, and
// the running conversation history for follow-ups. Centralizing this here
// (rather than in page.tsx local state) lets QueryPanel, SourcePanel, and the
// mind map all read the same state without prop drilling.

import { create } from "zustand";
import {
  ApiError,
  askQuery,
  askQueryStreaming,
  getQueryCapabilities,
  listDocuments,
  type ConversationTurn,
  type DocumentInfo,
  type GroundingSentence,
  type PipelineInfo,
  type QueryCapabilities,
  type QueryMode,
  type QueryOptions,
  type Source,
  type UnsupportedSentence,
} from "@/api/backendClient";

const MAX_CONVERSATION_TURNS = 6;

type AnswerState = {
  hasAnswer: boolean;
  currentAnswer: string;
  currentSources: Source[];
  confidenceScore: number;
  followupQuestions: string[];
  unsupportedSentences: UnsupportedSentence[];
  /** Per-sentence grounding verdicts from the active grounding method. */
  grounding: GroundingSentence[];
  /** True when the system declined to answer because retrieval confidence was too low. */
  abstained: boolean;
  /** Which optional NLP stages ran for the current answer. */
  pipeline: PipelineInfo | null;
  isStreaming: boolean;
  askedQuestion: string;
  queryId: string | null;
  timing: number;
  error: string | null;
};

const EMPTY_ANSWER: AnswerState = {
  hasAnswer: false,
  currentAnswer: "",
  currentSources: [],
  confidenceScore: 0,
  followupQuestions: [],
  unsupportedSentences: [],
  grounding: [],
  abstained: false,
  pipeline: null,
  isStreaming: false,
  askedQuestion: "",
  queryId: null,
  timing: 0,
  error: null,
};

type QueryStore = AnswerState & {
  mode: QueryMode;
  query: string;
  answerMode: QueryMode;
  asking: boolean;
  conversationHistory: ConversationTurn[];
  selectedDocIds: string[];
  selectedCollectionId: string | null;
  compareDocs: DocumentInfo[] | null;
  /** Per-query NLP options chosen in the UI (unset = server default). */
  options: QueryOptions;
  capabilities: QueryCapabilities | null;

  setOption: <K extends keyof QueryOptions>(key: K, value: QueryOptions[K] | undefined) => void;
  loadCapabilities: () => Promise<void>;
  setMode: (mode: QueryMode) => void;
  setQuery: (query: string) => void;
  setSelectedDocIds: (ids: string[]) => void;
  toggleSelectedDoc: (id: string) => void;
  loadCompareDocsIfNeeded: () => Promise<void>;
  startNewConversation: () => void;
  runQuery: (question: string, onUnauthorized: () => void) => Promise<void>;
};

export const useQueryStore = create<QueryStore>((set, get) => ({
  mode: "rag",
  query: "",
  answerMode: "rag",
  asking: false,
  conversationHistory: [],
  selectedDocIds: [],
  selectedCollectionId: null,
  compareDocs: null,
  options: {},
  capabilities: null,
  ...EMPTY_ANSWER,

  setOption: (key, value) =>
    set((s) => {
      const next = { ...s.options };
      if (value === undefined) delete next[key];
      else next[key] = value;
      return { options: next };
    }),
  loadCapabilities: async () => {
    if (get().capabilities !== null) return;
    try {
      set({ capabilities: await getQueryCapabilities() });
    } catch {
      // Older server without the endpoint: leave the advanced options hidden.
    }
  },

  setMode: (mode) => set({ mode }),
  setQuery: (query) => set({ query }),
  setSelectedDocIds: (ids) => set({ selectedDocIds: ids }),
  toggleSelectedDoc: (id) =>
    set((s) => ({
      selectedDocIds: s.selectedDocIds.includes(id)
        ? s.selectedDocIds.filter((d) => d !== id)
        : [...s.selectedDocIds, id],
    })),

  loadCompareDocsIfNeeded: async () => {
    if (get().compareDocs !== null) return;
    try {
      const docs = await listDocuments();
      set({ compareDocs: docs });
    } catch {
      set({ compareDocs: [] });
    }
  },

  startNewConversation: () => {
    set({ conversationHistory: [], ...EMPTY_ANSWER });
  },

  runQuery: async (q, onUnauthorized) => {
    const question = q.trim();
    const { mode, asking, selectedDocIds, conversationHistory, options } = get();
    if (!question || asking) return;
    if (mode === "compare" && selectedDocIds.length < 2) return;

    set({ asking: true, error: null });
    const start = performance.now();
    const opts = {
      conversation_history: conversationHistory,
      document_ids: mode === "compare" ? selectedDocIds : undefined,
      options: Object.keys(options).length > 0 ? options : undefined,
    };

    /** Appends this exchange to conversationHistory and trims to the last 3
     * exchanges (6 turns), so the next follow-up question carries it as
     * context. */
    function appendToConversation(answer: string) {
      set((s) => ({
        conversationHistory: [
          ...s.conversationHistory,
          { role: "user", content: question } as ConversationTurn,
          { role: "assistant", content: answer } as ConversationTurn,
        ].slice(-MAX_CONVERSATION_TURNS),
      }));
    }

    async function runBlocking() {
      const data = await askQuery(question, mode, opts);
      set({
        hasAnswer: true,
        currentAnswer: data.answer,
        currentSources: data.sources,
        confidenceScore: data.confidence_score,
        followupQuestions: data.followup_questions,
        unsupportedSentences: data.unsupported_sentences,
        grounding: data.grounding ?? [],
        abstained: data.abstained ?? false,
        pipeline: data.pipeline ?? null,
        askedQuestion: question,
        answerMode: mode,
        queryId: data.query_id,
        timing: (performance.now() - start) / 1000,
      });
      appendToConversation(data.answer);
    }

    let receivedSources = false;
    let streamedAnswer = "";
    try {
      for await (const event of askQueryStreaming(question, mode, opts)) {
        if (event.type === "sources") {
          receivedSources = true;
          set({
            hasAnswer: true,
            currentSources: event.sources,
            currentAnswer: "",
            grounding: [],
            abstained: false,
            pipeline: null,
            unsupportedSentences: [],
            askedQuestion: question,
            answerMode: mode,
            isStreaming: true,
          });
        } else if (event.type === "token") {
          streamedAnswer += event.token;
          set({ currentAnswer: streamedAnswer });
        } else if (event.type === "followups") {
          set({ followupQuestions: event.followups });
        } else if (event.type === "pipeline") {
          set({ pipeline: event.pipeline, abstained: event.abstained });
        } else if (event.type === "hallucination") {
          set((s) => ({
            unsupportedSentences: event.unsupported_sentences,
            grounding: event.grounding,
            pipeline: s.pipeline
              ? { ...s.pipeline, grounding_method: event.grounding_method, notes: event.notes }
              : s.pipeline,
          }));
        } else if (event.type === "done") {
          set({
            confidenceScore: event.confidence_score,
            queryId: event.query_id,
            timing: (performance.now() - start) / 1000,
          });
          appendToConversation(streamedAnswer);
        }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        onUnauthorized();
        return;
      }
      if (receivedSources) {
        // Failed partway through the stream — don't silently replace the
        // partial answer already on screen with a fresh (re-run) one.
        set({ error: e instanceof Error ? e.message : "The answer stream was interrupted." });
      } else {
        // Never got going (no SSE support, network hiccup, etc.) — fall back
        // to the blocking endpoint transparently.
        try {
          await runBlocking();
        } catch (e2) {
          if (e2 instanceof ApiError && e2.status === 401) {
            onUnauthorized();
            return;
          }
          set({
            error: e2 instanceof Error ? e2.message : "Something went wrong.",
            hasAnswer: false,
          });
        }
      }
    } finally {
      set({ isStreaming: false, asking: false });
    }
  },
}));

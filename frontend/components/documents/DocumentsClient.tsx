"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { api, type DocumentInfo } from "@/lib/api";

const ACCEPTED = ".md,.markdown,.txt,.html,.htm,.pdf";

export function DocumentsClient() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.documents();
      setDocs(res.documents);
      setTotal(res.total_chunks);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch on mount; setState runs after await
    void load();
  }, [load]);

  async function upload(files: File[]) {
    if (!files.length) return;
    setUploading(true);
    setNotice(null);
    setError(null);
    try {
      const res = await api.ingest(files);
      setNotice(
        `${res.total_inserted} chunk${res.total_inserted === 1 ? "" : "s"} inserted · index now ${res.index_chunks} chunks`,
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      const res = await api.deleteDocument(id);
      if (res && !res.ok) {
        setError(`Delete failed: ${res.status}`);
        return;
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-12">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <p className="eyebrow">Index · {total} chunks</p>
          <h1 className="mt-2 font-serif text-4xl tracking-tight text-ink">
            Documents
          </h1>
        </div>
        <button className="btn btn-ghost" onClick={() => void load()}>
          <RefreshCw size={14} /> Refresh
        </button>
      </header>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void upload(Array.from(e.dataTransfer.files));
        }}
        className={`card mb-8 flex flex-col items-center justify-center gap-2 border-dashed px-6 py-12 text-center transition-colors duration-150 ${
          dragging ? "border-accent bg-accent-soft/50" : ""
        }`}
      >
        <FileUp size={22} className="text-faint" strokeWidth={1.5} />
        <p className="text-sm font-medium text-ink">
          Drop documents to ingest, or{" "}
          <button
            className="text-accent underline underline-offset-2 hover:text-accent-hover"
            onClick={() => fileInput.current?.click()}
          >
            browse
          </button>
        </p>
        <p className="font-mono text-[0.6875rem] text-faint">
          PDF · Markdown · TXT · HTML
        </p>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => {
            void upload(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </div>

      {uploading && (
        <p className="mb-4 flex items-center gap-2 text-sm text-muted">
          <Loader2 size={14} className="animate-spin text-accent" /> Ingesting,
          chunking, deduplicating…
        </p>
      )}
      {notice && (
        <p className="mb-4 rounded-lg border border-ok/30 bg-ok/5 px-4 py-2.5 text-sm text-ok">
          {notice}
        </p>
      )}
      {error && (
        <p className="mb-4 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
          {error}
        </p>
      )}

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Loader2 size={14} className="animate-spin text-accent" /> Loading…
        </p>
      ) : docs.length === 0 ? (
        <p className="text-sm text-muted">
          No documents ingested yet. Drop files above to seed the index.
        </p>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-line">
                <th className="px-4 py-2.5 font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint">
                  Document
                </th>
                <th className="px-4 py-2.5 font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint">
                  Format
                </th>
                <th className="px-4 py-2.5 text-right font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint">
                  Chunks
                </th>
                <th className="px-4 py-2.5 text-right" aria-label="actions" />
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr
                  key={d.document_id}
                  className="border-b border-line last:border-0 hover:bg-paper"
                >
                  <td className="px-4 py-3 text-sm font-medium text-ink">
                    {d.document_id}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded border border-line bg-paper px-1.5 py-0.5 font-mono text-[0.6875rem] text-muted">
                      {d.format}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm tnum text-ink">
                    {d.chunk_count}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      className="rounded p-1.5 text-faint transition-colors hover:bg-danger/10 hover:text-danger"
                      aria-label={`Delete ${d.document_id}`}
                      onClick={() => void remove(d.document_id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

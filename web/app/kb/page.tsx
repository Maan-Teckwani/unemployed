"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type KBChunk } from "@/lib/api";
import { AddItemForm } from "@/components/kb/add-item-form";
import { ChunkList } from "@/components/kb/chunk-list";
import { SemanticSearch } from "@/components/kb/semantic-search";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export default function KBPage() {
  const [chunks, setChunks] = useState<KBChunk[]>([]);

  const refresh = useCallback(async () => {
    try {
      setChunks(await api.listChunks());
    } catch {
      // Backend not reachable yet — leave the list empty.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Knowledge Base</h1>
        <p className="text-muted-foreground mt-1">
          {chunks.length} accomplishment chunk{chunks.length === 1 ? "" : "s"} stored.
        </p>
      </div>

      <div className="rounded-lg border border-dashed p-4 flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          Fastest way to start: upload your resume &amp; documents and let them be
          parsed into chunks you can review.
        </p>
        <Link href="/kb/import" className={buttonVariants({ variant: "default" })}>
          Import from documents
        </Link>
      </div>

      <AddItemForm onAdded={refresh} />
      <SemanticSearch />

      <Separator />

      <div className="space-y-3">
        <h2 className="font-medium">Stored chunks</h2>
        <ChunkList chunks={chunks} onChanged={refresh} />
      </div>
    </div>
  );
}

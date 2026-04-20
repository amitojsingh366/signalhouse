"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Check, ImagePlus, Upload, X } from "lucide-react";
import { useParseScreenshot, useConfirmUpload } from "@/lib/hooks";
import type { UploadHolding } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";
import { UploadingSpinner } from "@/components/ui/loading";

export default function UploadPage() {
  const { toast } = useToast();
  const parseScreenshot = useParseScreenshot();
  const confirmUpload = useConfirmUpload();
  const [editing, setEditing] = useState<UploadHolding[] | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;

    setPreview(URL.createObjectURL(file));
    setEditing(null);

    try {
      const holdings = await parseScreenshot.mutateAsync(file);
      setEditing(holdings.map((h) => ({ ...h })));
      toast(`Parsed ${holdings.length} holdings from screenshot`, "success");
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to parse screenshot",
        "error"
      );
    }
  }, [parseScreenshot, toast]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".png", ".jpg", ".jpeg", ".webp"] },
    maxFiles: 1,
    disabled: parseScreenshot.isPending,
  });

  async function handleConfirm() {
    if (!editing) return;
    try {
      await confirmUpload.mutateAsync(editing);
      toast(`Synced ${editing.length} holdings to portfolio`, "success");
      setEditing(null);
      setPreview(null);
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Confirm failed",
        "error"
      );
    }
  }

  function handleCancel() {
    setEditing(null);
    setPreview(null);
  }

  function updateHolding(index: number, field: keyof UploadHolding, value: string) {
    if (!editing) return;
    const updated = [...editing];
    if (field === "symbol") {
      updated[index] = { ...updated[index], symbol: value };
    } else {
      updated[index] = { ...updated[index], [field]: parseFloat(value) || 0 };
    }
    setEditing(updated);
  }

  function removeHolding(index: number) {
    if (!editing) return;
    setEditing(editing.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Upload</h1>
          <p className="sub">
            Drop a brokerage screenshot to sync holdings and trades
            <span className="divider">·</span>
            Wealthsimple, Questrade, and IBKR formats supported
          </p>
        </div>
      </div>

      <div
        {...getRootProps()}
        className={cn(
          "card cursor-pointer border-2 border-dashed p-12 text-center transition-colors",
          isDragActive
            ? "border-brand-500 bg-brand-500/10"
            : "border-white/15 hover:border-white/30 hover:bg-white/[0.02]",
          parseScreenshot.isPending && "pointer-events-none opacity-60"
        )}
      >
        <input {...getInputProps()} />
        {parseScreenshot.isPending ? (
          <div className="mx-auto w-fit">
            <UploadingSpinner />
          </div>
        ) : (
          <>
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-300">
              <ImagePlus className="h-8 w-8" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">Drop a screenshot here</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">
              PNG, JPG, or WebP up to 20MB. We extract symbols, quantity, and value,
              then you confirm before syncing to the portfolio.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white">
              <Upload className="h-4 w-4" />
              Choose file
            </div>
          </>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {(preview || editing) && (
          <div className="space-y-6">
            {preview && (
              <div className="card overflow-hidden">
                <div className="head">
                  <h3>Screenshot preview</h3>
                  <span className="sub">input image</span>
                </div>
                <div className="body">
                  <img
                    src={preview}
                    alt="Uploaded screenshot"
                    className="w-full rounded-lg border border-white/10"
                  />
                </div>
              </div>
            )}

            {editing && (
              <div className="card">
                <div className="head">
                  <h3>Parsed holdings</h3>
                  <span className="sub">{editing.length} rows</span>
                </div>
                <div className="divide-y divide-white/5">
                  {editing.map((h, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-3">
                      <input
                        type="text"
                        value={h.symbol}
                        onChange={(e) => updateHolding(i, "symbol", e.target.value)}
                        className="w-24 rounded border border-white/10 bg-white/5 px-2 py-1 text-sm text-white outline-none focus:border-brand-500/50"
                      />
                      <input
                        type="number"
                        step="any"
                        value={h.quantity}
                        onChange={(e) => updateHolding(i, "quantity", e.target.value)}
                        className="w-20 rounded border border-white/10 bg-white/5 px-2 py-1 text-right text-sm text-white outline-none focus:border-brand-500/50"
                      />
                      <span className="text-xs text-slate-500">
                        {formatCurrency(h.market_value_cad)}
                      </span>
                      <button
                        onClick={() => removeHolding(i)}
                        className="ml-auto text-slate-600 hover:text-red-400"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-3 border-t border-white/10 p-4">
                  <button
                    onClick={handleConfirm}
                    disabled={confirmUpload.isPending || editing.length === 0}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-brand-600 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
                  >
                    <Check className="h-4 w-4" />
                    {confirmUpload.isPending ? "Confirming..." : "Confirm sync"}
                  </button>
                  <button
                    onClick={handleCancel}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10"
                  >
                    <X className="h-4 w-4" />
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="card">
          <div className="head">
            <h3>How OCR sync works</h3>
            <span className="sub">4 steps</span>
          </div>
          <div className="body">
            {[
              {
                title: "Scan image",
                text: "The uploaded screenshot is parsed for visible holdings rows.",
              },
              {
                title: "Match symbols",
                text: "Extracted tickers are validated against the TSX/CDR universe.",
              },
              {
                title: "Build changes",
                text: "Detected rows are transformed into holding updates.",
              },
              {
                title: "Confirm sync",
                text: "You review and approve before writing to your portfolio.",
              },
            ].map((step, i) => (
              <div key={step.title} className="flex gap-3 border-b border-white/5 py-3 last:border-b-0">
                <span className="mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-md border border-brand-500/30 bg-brand-500/10 font-mono text-xs text-brand-300">
                  {(i + 1).toString().padStart(2, "0")}
                </span>
                <div>
                  <p className="text-sm font-medium text-slate-100">{step.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">{step.text}</p>
                </div>
              </div>
            ))}

            <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.02] p-3 text-xs text-slate-400">
              OCR is assistive only. You should confirm all quantities and symbols before sync.
            </div>
          </div>
        </div>
      </div>

      {!preview && !editing && (
        <div className="card">
          <div className="head">
            <h3>Recent uploads</h3>
            <span className="sub">session activity</span>
          </div>
          <div className="body text-sm text-slate-500">
            No recent uploads in this session yet.
          </div>
        </div>
      )}
    </div>
  );
}

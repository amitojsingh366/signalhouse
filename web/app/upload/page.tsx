"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileImage, Check, X, Edit3 } from "lucide-react";
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
      <h1 className="text-2xl font-bold">Upload Screenshot</h1>
      <p className="text-sm text-slate-400">
        Upload a screenshot of your brokerage holdings to sync them with the bot.
        The vision model will parse the positions automatically.
      </p>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={cn(
          "glass-card flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors",
          isDragActive
            ? "border-brand-500 bg-brand-500/10"
            : "border-white/20 hover:border-white/40 hover:bg-white/5",
          parseScreenshot.isPending && "pointer-events-none opacity-50"
        )}
      >
        <input {...getInputProps()} />
        {parseScreenshot.isPending ? (
          <UploadingSpinner />
        ) : (
          <>
            <Upload className="mb-3 h-10 w-10 text-slate-500" />
            <p className="text-sm text-slate-300">
              {isDragActive
                ? "Drop screenshot here"
                : "Drag & drop a screenshot, or click to browse"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              PNG, JPG, or WebP — max one file
            </p>
          </>
        )}
      </div>

      {/* Preview + parsed results */}
      {(preview || editing) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Image preview */}
          {preview && (
            <div className="glass-card overflow-hidden">
              <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
                <FileImage className="h-4 w-4 text-slate-500" />
                <span className="text-sm text-slate-400">Screenshot Preview</span>
              </div>
              <div className="p-4">
                <img
                  src={preview}
                  alt="Uploaded screenshot"
                  className="w-full rounded-lg"
                />
              </div>
            </div>
          )}

          {/* Parsed holdings editor */}
          {editing && (
            <div className="glass-card">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Edit3 className="h-4 w-4 text-slate-500" />
                  <span className="text-sm text-slate-400">
                    Parsed Holdings ({editing.length})
                  </span>
                </div>
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
                      onChange={(e) =>
                        updateHolding(i, "quantity", e.target.value)
                      }
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

              {/* Actions */}
              <div className="flex gap-3 border-t border-white/10 p-4">
                <button
                  onClick={handleConfirm}
                  disabled={confirmUpload.isPending || editing.length === 0}
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-brand-600 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
                >
                  <Check className="h-4 w-4" />
                  {confirmUpload.isPending ? "Confirming..." : "Confirm"}
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
    </div>
  );
}

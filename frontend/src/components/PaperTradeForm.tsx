import React, { Fragment, useEffect, useState } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { useForm } from "@tanstack/react-form";
import { z } from "zod";
import { toast } from "react-toastify";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IconAlertTriangle } from "@tabler/icons-react";
import { api } from "../lib/api";

const FASTAPI_BASE = "http://localhost:8000";
const NEST_BASE = "http://localhost:3000";

const tradeSchema = z.object({
  stockName: z.string().min(1, "Stock symbol required"),
  quantity: z.coerce.number().min(1, "Qty >= 1"),
  price: z.coerce.number().min(0.01, "Price required"),
  type: z.enum(["buy", "sell"]),
  message: z.string().optional(),
});

type TradeValues = z.infer<typeof tradeSchema>;

type Props = {
  edit?: boolean;
  id?: number | string;
  toggle: () => void;
  isOpen: boolean;
  defaultValues?: Partial<TradeValues & { stockName: string; quantity: string; price: number; message: string; type: string }>;
  queryKey: readonly unknown[];
};

export default function PaperTradeForm({
  edit = false,
  id = 0,
  toggle,
  isOpen,
  defaultValues = { stockName: "", price: 0, message: "", quantity: "1" as any, type: "buy" },
  queryKey,
}: Props) {
  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-10" onClose={toggle}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-25" />
        </Transition.Child>
        {isOpen && (
          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-xl transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                    {edit ? "Edit Item" : "Paper Trade — Realistic Execution"}
                  </Dialog.Title>
                  <FormInner edit={edit} id={id} toggle={toggle} defaultValues={defaultValues as any} queryKey={queryKey} />
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        )}
      </Dialog>
    </Transition>
  );
}

function FormInner({ edit, id, toggle, defaultValues, queryKey }: Props) {
  const queryClient = useQueryClient();

  // fetch NSE symbols for async select from GET http://localhost:3000/stock-exchange/Nse
  const { data: optionsNse } = useQuery({
    queryFn: () => api<string[]>(`${NEST_BASE}/stock-exchange/Nse`),
    queryKey: ["NseStockName"],
    cacheTime: Infinity as any,
    staleTime: Infinity as any,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    select: (d: any) => d.data?.map((c: string) => ({ value: c, label: c })) || [],
  });

  const form = useForm({
    defaultValues: {
      stockName: (defaultValues as any)?.stockName ?? "",
      quantity: Number((defaultValues as any)?.quantity ?? 1),
      price: Number((defaultValues as any)?.price ?? 0),
      type: ((defaultValues as any)?.type ?? "buy") as "buy" | "sell",
      message: (defaultValues as any)?.message ?? "",
    } as TradeValues,
    onSubmit: async ({ value }) => {
      const parsed = tradeSchema.safeParse(value);
      if (!parsed.success) {
        toast.error(parsed.error.issues[0]?.message ?? "Validation failed");
        return;
      }
      await tradeMutation.mutateAsync(parsed.data);
    },
  });

  // track symbol for LTP + execution preview without violating rules of hooks via Subscribe
  const [symbolWatch, setSymbolWatch] = useState<string>((defaultValues as any)?.stockName ?? "");
  const [qtyWatch, setQtyWatch] = useState<number>(Number((defaultValues as any)?.quantity ?? 1));

  // LTP fetch
  const { data: Prices } = useQuery({
    queryFn: () => api<any>(`${NEST_BASE}/stock-exchange/${symbolWatch}`),
    queryKey: ["NSE_LasT_TradedPrice", symbolWatch],
    enabled: !!symbolWatch,
    staleTime: Infinity as any,
    cacheTime: Infinity as any,
    refetchOnWindowFocus: false,
    select: (d) => d || {},
  });

  // auto-fill price when LTP loads (and not editing? but still fill if empty)
  useEffect(() => {
    if (Prices?.lastTradedPrice) {
      // only auto-fill if price is empty or matches previous LTP
      const currentPrice = (form as any).getFieldValue?.("price");
      if (!currentPrice || currentPrice === 0) {
        (form as any).setFieldValue("price", Prices.lastTradedPrice);
      } else {
        // update anyway to reflect current LTP if user hasn't manually edited? we update silently
        // uncomment to always sync: (form as any).setFieldValue("price", Prices.lastTradedPrice);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Prices?.lastTradedPrice]);

  // execution preview query
  const { data: executionPreview, isFetching: previewLoading } = useQuery({
    queryFn: async () => {
      try {
        return await api<any>(`${FASTAPI_BASE}/quant/execution/simulate`, {
          method: "POST",
          body: JSON.stringify({ symbol: symbolWatch, qty: Number(qtyWatch) }),
        });
      } catch {
        try {
          return await api<any>(`${NEST_BASE}/quant/execution/simulate`, {
            method: "POST",
            body: JSON.stringify({ symbol: symbolWatch, qty: Number(qtyWatch) }),
          });
        } catch {
          // mock fallback for demo
          const ideal = Prices?.lastTradedPrice ?? 300;
          const slippage = 0.008;
          const realistic = Number((ideal * (1 + slippage)).toFixed(2));
          return {
            idealPrice: ideal,
            realisticPrice: realistic,
            slippagePct: 0.8,
            feasibleQty: Math.min(Number(qtyWatch), 200),
            requestedQty: Number(qtyWatch),
            volume: 5000,
            illiquid: true,
            warning: "illiquid",
          };
        }
      }
    },
    queryKey: ["executionPreview", symbolWatch, qtyWatch],
    enabled: !!symbolWatch && !!qtyWatch && Number(qtyWatch) > 0,
    staleTime: 30_000 as any,
  });

  const tradeMutation = useMutation({
    mutationFn: async (values: TradeValues) => {
      // Prefer FastAPI /trades, fallback to Nest /stocks
      const payload = {
        stockName: values.stockName,
        quantity: String(values.quantity),
        price: Number(values.price),
        type: values.type,
        message: values.message ?? "",
        username: "MBSKS",
      };
      const body = JSON.stringify(payload);
      try {
        return await api<any>(`${FASTAPI_BASE}/trades`, { method: "POST", body });
      } catch {
        // fallback to Nest stocks endpoint to keep app functional
        if (edit) {
          return await api<any>(`${NEST_BASE}/stocks/${id}`, { method: "PATCH", body });
        }
        return await api<any>(`${NEST_BASE}/stocks`, { method: "POST", body });
      }
    },
    onError(error) {
      toast.error("Error while " + (edit ? "editing" : "adding") + " your trade");
      console.error(error);
    },
    onSuccess(res: any) {
      // keep queryKey ["Stocks", Duration, AllDatas] pattern from Home.tsx:16
      queryClient.invalidateQueries(queryKey as any);
      queryClient.setQueryData(queryKey as any, (oldData: any) => {
        toast.success("Item was " + (edit ? "edited" : "added") + " successfully");
        const created = res?.data ?? res;
        if (Array.isArray(oldData)) {
          return edit ? [...oldData.filter((d: any) => d.id != id), created] : [...oldData, created];
        }
        if (oldData?.data) {
          return {
            ...oldData,
            data: edit ? [...oldData.data.filter((d: any) => d.id != id), created] : [...oldData.data, created],
          };
        }
        return oldData;
      });
      toggle();
    },
  });

  return (
    <section aria-labelledby="payment-heading" className="flex-auto overflow-y-auto px-1 pt-5 pb-9 sm:px-3">
      <div className="max-w-lg mx-auto lg:pt-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
            form.handleSubmit();
          }}
          className="grid gap-y-4"
        >
          {/* type */}
          <form.Field
            name="type"
            validators={{
              onChange: ({ value }) => (!value ? "Type required" : undefined),
            }}
            children={(field) => (
              <div className="mb-2">
                <label className="block text-sm font-medium text-gray-700">Type</label>
                <select
                  value={field.state.value as string}
                  onChange={(e) => field.handleChange(e.target.value as any)}
                  onBlur={field.handleBlur}
                  className="block focus:ring-indigo-500 focus:border-indigo-500 shadow-sm w-full sm:text-sm border-gray-300 rounded-md mt-1"
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
                {field.state.meta.errors?.length ? (
                  <p className="text-xs text-red-600 mt-1">{String(field.state.meta.errors[0])}</p>
                ) : null}
              </div>
            )}
          />

          {/* stockName async select */}
          <form.Field
            name="stockName"
            validators={{
              onChange: ({ value }) => {
                const r = z.string().min(1).safeParse(value);
                return r.success ? undefined : "Stock required";
              },
            }}
            children={(field) => (
              <div>
                <label className="block text-sm font-medium text-gray-700">Name of Stock</label>
                <div className="mt-1">
                  {/* searchable select using input + datalist */}
                  <input
                    list="nse-symbols"
                    value={field.state.value as string}
                    onChange={(e) => {
                      field.handleChange(e.target.value as any);
                      setSymbolWatch(e.target.value);
                    }}
                    onBlur={field.handleBlur}
                    placeholder="Search symbol e.g. RELIANCE"
                    className="focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md shadow-sm px-3 py-2"
                  />
                  <datalist id="nse-symbols">
                    {(optionsNse ?? []).slice(0, 200).map((o: any) => (
                      <option key={o.value} value={o.value} />
                    ))}
                  </datalist>
                  {field.state.meta.errors?.length ? (
                    <p className="text-xs text-red-600 mt-1">{String(field.state.meta.errors[0])}</p>
                  ) : null}
                  {field.state.value ? (
                    <p className="text-xs text-gray-500 mt-1">
                      Selected: <span className="font-medium">{String(field.state.value)}</span>{" "}
                      {Prices?.lastTradedPrice ? `— LTP ₹${Prices.lastTradedPrice}` : ""}
                    </p>
                  ) : null}
                </div>
              </div>
            )}
          />

          {/* quantity */}
          <form.Field
            name="quantity"
            validators={{
              onChange: ({ value }) => {
                const r = z.coerce.number().min(1).safeParse(value);
                return r.success ? undefined : "Qty >=1";
              },
            }}
            children={(field) => (
              <div>
                <label className="block text-sm font-medium text-gray-700">Quantity</label>
                <div className="mt-1">
                  <input
                    type="number"
                    value={field.state.value as number}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      field.handleChange(v as any);
                      setQtyWatch(v);
                    }}
                    onBlur={field.handleBlur}
                    className="focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md px-3 py-2"
                    placeholder="0"
                    min={1}
                  />
                  {field.state.meta.errors?.length ? (
                    <p className="text-xs text-red-600 mt-1">{String(field.state.meta.errors[0])}</p>
                  ) : null}
                </div>
              </div>
            )}
          />

          {/* price auto-fill LTP */}
          <form.Field
            name="price"
            validators={{
              onChange: ({ value }) => {
                const r = z.coerce.number().min(0.01).safeParse(value);
                return r.success ? undefined : "Price required";
              },
            }}
            children={(field) => (
              <div>
                <label className="block text-sm font-medium text-gray-700">Price</label>
                <div className="mt-1 relative rounded-md shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-gray-500 sm:text-sm">₹</span>
                  </div>
                  <input
                    type="number"
                    step={0.01}
                    value={field.state.value as number}
                    onChange={(e) => field.handleChange(Number(e.target.value) as any)}
                    onBlur={field.handleBlur}
                    className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md py-2"
                    placeholder="0.00"
                  />
                  <div className="absolute inset-y-0 right-0 pr-3 hidden lg:flex items-center pointer-events-none">
                    <span className="text-gray-500 sm:text-sm">Rupee</span>
                  </div>
                </div>
                {Prices?.lastTradedPrice ? (
                  <button
                    type="button"
                    onClick={() => field.handleChange(Prices.lastTradedPrice as any)}
                    className="text-xs text-indigo-600 mt-1 hover:underline"
                  >
                    Use LTP {Prices.lastTradedPrice}
                  </button>
                ) : null}
                {field.state.meta.errors?.length ? (
                  <p className="text-xs text-red-600 mt-1">{String(field.state.meta.errors[0])}</p>
                ) : null}
                {symbolWatch && (
                  <div className="flex gap-3 text-xs text-gray-600 mt-2">
                    <span>LTP: {Prices?.lastTradedPrice ?? "-"}</span>
                    <span>52WL: {Prices?.fiftyTwoWeekLow ?? "-"}</span>
                    <span>52WH: {Prices?.fiftyTwoWeekHigh ?? "-"}</span>
                  </div>
                )}
              </div>
            )}
          />

          {/* comment */}
          <form.Field
            name="message"
            children={(field) => (
              <div>
                <label className="block text-sm font-medium text-gray-700">Add your comment</label>
                <div className="mt-1">
                  <textarea
                    rows={4}
                    value={(field.state.value as string) ?? ""}
                    onChange={(e) => field.handleChange(e.target.value as any)}
                    onBlur={field.handleBlur}
                    className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md px-3 py-2"
                  />
                </div>
              </div>
            )}
          />

          {/* Realistic execution preview BEFORE submit */}
          {symbolWatch && qtyWatch ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 mt-2">
              <div className="flex items-start gap-2">
                <IconAlertTriangle size={18} className="text-amber-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm">
                  <p className="font-medium text-amber-900">Realistic Execution Preview</p>
                  {previewLoading ? (
                    <p className="text-gray-500 text-xs mt-1">Simulating…</p>
                  ) : executionPreview ? (
                    <p className="text-gray-700 mt-1 leading-relaxed">
                      Ideal: {executionPreview.idealPrice ?? executionPreview.ideal ?? 300} | Realistic buy: {executionPreview.realisticPrice ?? executionPreview.realistic ?? 302.5} (slippage{" "}
                      {executionPreview.slippagePct ?? executionPreview.slippage ?? "0.8"}%) | Feasible:{" "}
                      {executionPreview.feasibleQty ?? executionPreview.feasible ?? 200}/
                      {executionPreview.requestedQty ?? qtyWatch} shares (volume{" "}
                      {executionPreview.volume ?? "5K"}) | Warning: {executionPreview.warning ?? (executionPreview.illiquid ? "illiquid" : "—")}
                    </p>
                  ) : (
                    <p className="text-gray-500 text-xs mt-1">Enter symbol & qty to preview</p>
                  )}
                  {executionPreview?.illiquid || executionPreview?.warning === "illiquid" ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 mt-2">
                      <IconAlertTriangle size={14} /> illiquid — order may not fully fill
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          <form.Subscribe
            selector={(state) => [state.canSubmit, state.isSubmitting]}
            children={([canSubmit, isSubmitting]: any) => (
              <button
                type="submit"
                disabled={!canSubmit}
                className="w-full mt-4 bg-indigo-600 border border-transparent rounded-md shadow-sm py-2 px-4 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                {isSubmitting ? "Submitting…" : edit ? "Edit Stock" : "Add Stock"}
              </button>
            )}
          />
          <button
            type="button"
            onClick={() => form.reset()}
            className="w-full mt-2 bg-white border border-gray-300 rounded-md shadow-sm py-2 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Reset Form Data
          </button>
        </form>
      </div>
    </section>
  );
}
